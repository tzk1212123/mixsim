"""Shared experiment service used by Python, HTTP/CLI and the MCP bridge."""

import json
import math
import random
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from . import __version__
from .config import RigConfig
from .physics import color_error, color_rgb
from .rig import Rig, RigError, finite


def audit_safe(value):
    """Rejected Python inputs must remain exportable as strict JSON."""
    if isinstance(value, float) and not math.isfinite(value):
        return repr(value)
    if isinstance(value, dict):
        return {str(k): audit_safe(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [audit_safe(v) for v in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return repr(value)


class DeviceBackend(Protocol):
    """Future bench adapter contract. Bench drivers must also enforce their envelope."""
    config: RigConfig
    interlock: str | None
    events: list[dict]

    def set_flows(self, a_ul_min: float, b_ul_min: float) -> dict: ...
    def snapshot(self) -> dict: ...
    def camera(self) -> dict: ...
    def advance(self, seconds: float) -> dict: ...
    def stop(self, reason: str = "operator") -> dict: ...
    def reset_interlock(self) -> dict: ...
    def write_channel(self, device: str, channel: str, value: float) -> dict: ...


class LabService:
    def __init__(self, config: RigConfig | None = None, seed: int = 42, target_fraction: float = 0.68):
        self.lock = threading.RLock()
        self.config = config or RigConfig()
        self.new_session(seed, target_fraction)

    def new_session(self, seed=42, target_fraction=0.68):
        fraction = finite(target_fraction, "target_fraction")
        if not 0 <= fraction <= 1:
            raise RigError("target_range", "Target nominal A fraction must be in [0, 1]")
        # Validate before replacing a session.
        rig = Rig(self.config, seed)
        self.rig = rig
        self.target_fraction = fraction
        self.target_rgb = color_rgb(fraction, self.config)
        self.records: list[dict] = []
        self.audit: list[dict] = []
        self.recommendation: int | None = None
        self.final_record: int | None = None
        self.created_at = datetime.now(timezone.utc).isoformat()
        self._plan_rng = random.Random(seed + 3001)
        return self.public_state()

    def devices(self):
        c = self.config
        return {"mode": "simulation", "standard": "MHS-style; not official MHS compliance",
                "devices": [
                    {"id": "pump_a", "model": "NE-1000-inspired", "syringe": c.syringe.to_dict(), "channels": {"flow_ul_min": "read/write", "remaining_ul": "read", "syringe": "read"}},
                    {"id": "pump_b", "model": "NE-1000-inspired", "syringe": c.syringe.to_dict(), "channels": {"flow_ul_min": "read/write", "remaining_ul": "read", "syringe": "read"}},
                    {"id": "daq", "model": "USB-6003-inspired", "channels": {"pressure_kpa": "read", "pressure_voltage_v": "read", "temperature_c": "read", "heater": "read-only disabled"}},
                    {"id": "camera", "model": "synthetic RGB ROI camera", "channels": {"rgb": "read"}}],
                "device_capability": {"syringe_profile": c.syringe_profile,
                                      "min_nonzero_per_pump_ul_min": c.syringe.min_flow_ul_min,
                                      "max_per_pump_ul_min": c.syringe.max_flow_ul_min},
                "envelope": {"basis": "assumed project limits, not manufacturer safety ratings",
                             "max_per_pump_ul_min": c.max_flow_ul_min, "max_total_ul_min": c.max_total_flow_ul_min,
                             "pressure_trip_kpa": c.pressure_trip_kpa, "pressure_reset_kpa": c.pressure_reset_kpa},
                "target_rgb": self.target_rgb.copy(), "objective": "Minimize RGB RMSE in digital numbers (0..255)",
                "tolerance_rgb_dn": 3.0, "time": "virtual; explicit advance only"}

    def read(self, device):
        state = self.rig.snapshot()
        if device == "camera":
            return self.rig.camera()
        if device == "daq":
            return state["daq"] | {"heater_enabled": False}
        if device in ("pump_a", "pump_b"):
            i = 0 if device == "pump_a" else 1
            return {"flow_ul_min": state["commanded_ul_min"][i], "remaining_ul": state["remaining_ul"][i],
                    "syringe": self.config.syringe.to_dict()}
        if device == "rig":
            return state
        raise RigError("unknown_device", f"Unknown device {device}")

    def reference(self, device):
        if device not in ("pump", "daq", "camera"):
            raise RigError("unknown_device", "Reference device must be pump, daq or camera")
        text = (Path(__file__).parent / "references" / f"{device}.md").read_text(encoding="utf-8")
        if device == "pump":
            s = self.config.syringe
            text += (f"\nActive session: profile={self.config.syringe_profile}; {s.manufacturer}; "
                     f"capacity={s.capacity_ml:g} mL; inside diameter={s.inside_diameter_mm:g} mm; "
                     f"nonzero device flow={s.min_flow_ul_min:g}..{s.max_flow_ul_min:g} uL/min. "
                     f"Project per-pump limit={self.config.max_flow_ul_min:g} uL/min; "
                     f"combined limit={self.config.max_total_flow_ul_min:g} uL/min.\n")
        return {"device": device, "text": text}

    def experiment(self, a_ul_min, b_ul_min, settle_s=60, label="manual", kind="trial"):
        if self.final_record is not None:
            raise RigError("campaign_complete", "Start a new session to run another campaign")
        settle_s = finite(settle_s, "settle_s")
        if not 1 <= settle_s <= 600:
            raise RigError("settle_range", "settle_s must be in [1, 600]")
        a, b = finite(a_ul_min, "a_ul_min"), finite(b_ul_min, "b_ul_min")
        if a + b <= 0:
            raise RigError("zero_total_flow", "An experiment requires nonzero combined flow")
        if not isinstance(label, str) or len(label) > 120:
            raise RigError("label_limit", "label must be a string of at most 120 characters")
        self.rig.set_flows(a, b)
        started = self.rig.time_s
        try:
            self.rig.advance(settle_s)
            camera = self.rig.camera()
            record = {"id": len(self.records) + 1, "kind": kind, "label": label,
                      "started_s": round(started, 6), "finished_s": round(self.rig.time_s, 6),
                      "a_ul_min": a, "b_ul_min": b, "settle_s": settle_s,
                      "rgb": camera["rgb"], "frames": camera["frames"],
                      "error_rgb_dn": color_error(camera["rgb"], self.target_rgb),
                      "pressure_kpa": self.rig.snapshot()["daq"]["pressure_kpa"],
                      "status": "aborted" if self.rig.interlock else "ok",
                      "interlock": self.rig.interlock,
                      # Approximate washout guidance, not a measured settling certificate.
                      "suggested_settle_s": self.suggested_settle(a + b),
                      "recommended_from": self.recommendation if kind == "replicate" else None}
            self.records.append(record)
            if kind == "trial":
                self.recommendation = None
            return record
        finally:
            self.rig.stop("experiment_end")

    def suggested_settle(self, total):
        c = self.config
        return round(5 * c.pump_tau_s + (c.transport_volume_ul + 6 * c.mixing_volume_ul) * 60 / total, 3)

    def recommend(self, record_id):
        if self.final_record is not None:
            raise RigError("campaign_complete", "Campaign already finalized")
        if type(record_id) is not int:
            raise RigError("invalid_record", "record_id must be an integer")
        match = next((r for r in self.records if r["id"] == record_id and r["kind"] == "trial" and r["status"] == "ok"), None)
        if match is None:
            raise RigError("invalid_record", "Choose a successful trial record")
        self.recommendation = record_id
        return {"recommended_record_id": record_id, "a_ul_min": match["a_ul_min"], "b_ul_min": match["b_ul_min"],
                "observed_error_rgb_dn": match["error_rgb_dn"], "delivered_error_rgb_dn": None,
                "next_step": "Call finalize to independently rerun this setting"}

    def finalize(self):
        if self.final_record is not None:
            raise RigError("campaign_complete", "Final replicate already exists")
        if self.recommendation is None:
            raise RigError("recommendation_required", "Select a recommendation before final replication")
        trial = next(r for r in self.records if r["id"] == self.recommendation)
        result = self.experiment(trial["a_ul_min"], trial["b_ul_min"], trial["settle_s"], "Independent final replicate", "replicate")
        if result["status"] == "ok":
            self.final_record = result["id"]
        return result

    def next_baseline(self, planner="feedback", total_ul_min=400.0, settle_s=60.0):
        """Only measured camera output is consulted. Not an LLM planner."""
        total = finite(total_ul_min, "total_ul_min")
        if not 1 <= total <= min(self.config.max_total_flow_ul_min, self.config.max_flow_ul_min):
            raise RigError("baseline_total", "Baseline total must be >=1 and <= a single-pump flow limit")
        if planner not in ("feedback", "random"):
            raise RigError("unknown_planner", "Use feedback or random")
        trials = [r for r in self.records if r["kind"] == "trial" and r["status"] == "ok"]
        if planner == "random":
            fraction = self._plan_rng.uniform(0.02, 0.98)
        else:
            lo, hi = 0.0, 1.0
            direction = [a - b for a, b in zip(color_rgb(1, self.config), color_rgb(0, self.config))]
            for r in trials:
                f = r["a_ul_min"] / (r["a_ul_min"] + r["b_ul_min"])
                signed = sum((m - t) * d for m, t, d in zip(r["rgb"], self.target_rgb, direction))
                if signed > 0:
                    hi = min(hi, f)
                else:
                    lo = max(lo, f)
            fraction = (lo + hi) / 2 if lo <= hi else 0.5
        return self.experiment(total * fraction, total * (1 - fraction), settle_s, f"{planner} baseline")

    def public_state(self):
        return {"version": __version__, "seed": self.rig.seed, "created_at": self.created_at,
                "target_rgb": self.target_rgb.copy(), "target_nominal_fraction_a": self.target_fraction,
                "rig": self.rig.snapshot(), "config": self.config.to_dict(),
                "syringe_specification": self.config.syringe.to_dict(),
                "records": self.records.copy(), "events": self.rig.events[-80:],
                "recommendation": self.recommendation, "final_record": self.final_record,
                "display_truth": self.rig.display_truth(),
                "notice": "Simulation only. Synthetic dye optics and assumed geometry. No hardware connected."}

    def export(self):
        return {"schema_version": 1, "model_version": __version__, "created_at": self.created_at,
                "seed": self.rig.seed, "configuration": self.config.to_dict(),
                "syringe_specification": self.config.syringe.to_dict(), "target_rgb": self.target_rgb,
                "target_nominal_fraction_a": self.target_fraction,
                "records": self.records.copy(), "recommendation": self.recommendation,
                "final_record": self.final_record, "events": self.rig.events.copy(), "audit": self.audit.copy(),
                "interpretation": "Use final_record for delivered performance; trials are observations. Model assumptions are not bench measurements."}

    def dispatch(self, action: str, params: dict | None = None, source="python"):
        params = params or {}
        with self.lock:
            functions = {"devices": self.devices, "reference": self.reference, "read": self.read,
                         "set_flows": self.rig.set_flows, "write": self.rig.write_channel,
                         "advance": self.rig.advance, "stop": self.rig.stop,
                         "reset_interlock": self.rig.reset_interlock, "inject_clog": self.rig.set_clog,
                         "experiment": self.experiment, "recommend": self.recommend,
                         "finalize": self.finalize, "baseline_step": self.next_baseline,
                         "new_session": self.new_session}
            # kind is internal: callers cannot turn an ordinary trial into a final replicate.
            if action == "experiment" and "kind" in params:
                return {"ok": False, "error": {"code": "invalid_arguments", "message": "kind is internal"}}
            entry = {"action": action, "params": audit_safe(params), "source": source, "time_s": self.rig.time_s}
            try:
                if action not in functions:
                    raise RigError("unknown_action", f"Unknown action {action}")
                result = functions[action](**params)
                entry["ok"] = True
                self.audit.append(entry)
                return {"ok": True, "result": result}
            except (RigError, TypeError, ValueError) as exc:
                entry["ok"] = False
                self.audit.append(entry)
                return {"ok": False, "error": {"code": getattr(exc, "code", "invalid_arguments"), "message": str(exc)}}


def save_run(service: LabService, path: str | Path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(service.export(), ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")

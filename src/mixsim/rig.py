"""Stateful virtual drivers. Every caller goes through this safety boundary."""

import math
import random
from collections import deque
from .config import RigConfig
from .physics import color_rgb, pressure_kpa


class RigError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def finite(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise RigError("invalid_number", f"{name} must be a finite number")
    return float(value)


class Rig:
    def __init__(self, config: RigConfig | None = None, seed: int = 42):
        self.config = config or RigConfig()
        if type(seed) is not int or not 0 <= seed <= 2**32 - 1:
            raise RigError("invalid_seed", "seed must be an integer in [0, 2**32-1]")
        self.seed = seed
        calibration = random.Random(seed)
        self._bias = [max(0.5, calibration.gauss(1, self.config.calibration_sd)) for _ in range(2)]
        self._camera_rng = random.Random(seed + 1001)
        self._daq_rng = random.Random(seed + 2001)
        self.time_s = 0.0
        self.commanded = [0.0, 0.0]
        self.actual = [0.0, 0.0]
        self.remaining = [self.config.syringe_capacity_ul] * 2
        self._pressure = 0.0
        self._fraction_a = 0.5
        self._transport = deque([(self.config.transport_volume_ul, 0.5)])
        self.clog_factor = 1.0
        self.interlock: str | None = None
        self.events: list[dict] = []
        self._cached_daq = self._measure_daq()

    def _event(self, kind, **data):
        self.events.append({"time_s": round(self.time_s, 6), "kind": kind, **data})

    def _reject(self, code, message, **data):
        self._event("rejected", code=code, message=message, **data)
        raise RigError(code, message)

    def set_flows(self, a_ul_min, b_ul_min):
        # Atomic: both validated before either is modified.
        try:
            values = [finite(a_ul_min, "a_ul_min"), finite(b_ul_min, "b_ul_min")]
        except RigError as exc:
            self._reject(exc.code, str(exc))
        syringe = self.config.syringe
        if any(v < 0 for v in values):
            self._reject("flow_limit", "Infusion-only flow must be nonnegative", requested=values)
        if any(v > syringe.max_flow_ul_min for v in values):
            self._reject("device_flow_limit", f"{syringe.manufacturer} {syringe.capacity_ml:g} mL device limit is {syringe.max_flow_ul_min:g} uL/min", requested=values)
        if any(v > self.config.max_flow_ul_min for v in values):
            self._reject("flow_limit", f"Project per-pump limit is {self.config.max_flow_ul_min:g} uL/min", requested=values)
        if any(0 < v < syringe.min_flow_ul_min for v in values):
            self._reject("flow_minimum", f"{syringe.manufacturer} {syringe.capacity_ml:g} mL minimum nonzero flow is {syringe.min_flow_ul_min:g} uL/min")
        if sum(values) > self.config.max_total_flow_ul_min:
            self._reject("total_flow_limit", f"Combined flow must be <= {self.config.max_total_flow_ul_min} uL/min")
        if self.interlock and any(values):
            self._reject("interlock_latched", "Stop, clear the fault and reset the interlock before pumping")
        if any(v > 0 and rem <= 0 for v, rem in zip(values, self.remaining)):
            self._reject("syringe_empty", "Refill requires a fresh simulation session")
        self.commanded = values
        self._event("set_flows", a_ul_min=values[0], b_ul_min=values[1])
        return self.snapshot()

    def stop(self, reason="operator"):
        # Idealized fast stop, not a model of real pressure relief or motor braking.
        self.commanded = [0.0, 0.0]
        self.actual = [0.0, 0.0]
        self._event("stop", reason=reason)
        return self.snapshot()

    def _trip(self, reason):
        if self.interlock is None:
            self.interlock = reason
            self._event("interlock", reason=reason, pressure_kpa=self._pressure)
            self.stop(reason)

    def reset_interlock(self):
        if any(self.commanded) or any(self.actual) or self._pressure >= self.config.pressure_reset_kpa:
            self._reject("reset_unsafe", "Stop pumps and advance until pressure is below reset threshold")
        if self.clog_factor > 1:
            self._reject("fault_present", "Clear simulated clog before resetting")
        if any(r <= 0 for r in self.remaining):
            self._reject("syringe_empty", "Empty syringe requires a fresh session")
        self.interlock = None
        self._event("reset_interlock")
        return self.snapshot()

    def set_clog(self, factor):
        factor = finite(factor, "factor")
        if not 1 <= factor <= 20:
            self._reject("clog_range", "Simulated clog resistance multiplier must be in [1, 20]")
        self.clog_factor = factor
        self._event("fault_injection", clog_factor=factor)
        return self.snapshot()

    def write_channel(self, device, channel, value):
        if device == "daq" and channel in ("heater", "temperature_c", "pressure_kpa"):
            self._reject("read_only", "DAQ and heater channels are read-only in this project")
        if device in ("pump_a", "pump_b") and channel == "flow_ul_min":
            values = self.commanded.copy()
            values[0 if device == "pump_a" else 1] = value
            return self.set_flows(*values)
        self._reject("unknown_channel", f"No writable channel {device}.{channel}")

    def _advect(self, volume, fraction):
        self._transport.append((volume, fraction))
        left, mass = volume, 0.0
        while left > 1e-12:
            available, f = self._transport.popleft()
            taken = min(available, left)
            mass += taken * f
            left -= taken
            if available - taken > 1e-12:
                self._transport.appendleft((available - taken, f))
        return mass / volume

    def advance(self, seconds):
        seconds = finite(seconds, "seconds")
        if not 0 < seconds <= 600:
            self._reject("duration_limit", "Advance duration must be in (0, 600] seconds")
        count = math.ceil(seconds / self.config.integration_step_s)
        dt = seconds / count
        for _ in range(count):
            self.time_s += dt
            for i in range(2):
                target = self.commanded[i] * self._bias[i]
                self.actual[i] += (target - self.actual[i]) * (-math.expm1(-dt / self.config.pump_tau_s))
                used = self.actual[i] * dt / 60
                if used >= self.remaining[i] and self.actual[i] > 0:
                    # Deliver only the remaining volume during this step.
                    self.actual[i] = self.remaining[i] * 60 / dt
                    self.remaining[i] = 0.0
                else:
                    self.remaining[i] = max(0, self.remaining[i] - used)
            total = sum(self.actual)
            equilibrium = pressure_kpa(total, self.config, self.clog_factor)
            self._pressure += (equilibrium - self._pressure) * (-math.expm1(-dt / self.config.pressure_tau_s))
            if total > 1e-12:
                volume = total * dt / 60
                inlet = self._advect(volume, self.actual[0] / total)
                self._fraction_a += (inlet - self._fraction_a) * (-math.expm1(-volume / self.config.mixing_volume_ul))
            self._cached_daq = self._measure_daq()
            # Trip on the sampled/quantized DAQ reading, not the planner's model.
            if self._cached_daq["pressure_kpa"] >= self.config.pressure_trip_kpa:
                self._trip("overpressure")
            if any(v <= 0 for v in self.remaining):
                self._trip("syringe_empty")
        self._event("advance", seconds=seconds)
        return self.snapshot()

    def _measure_daq(self):
        c = self.config
        noisy = min(c.pressure_sensor_span_kpa, max(0, self._pressure + self._daq_rng.gauss(0, c.pressure_noise_kpa)))
        # Hypothetical 0..100 kPa transducer -> 0..5 V, sampled on +-10 V 16-bit AI.
        volts = noisy / c.pressure_sensor_span_kpa * 5
        step = 20 / 65536
        voltage = round(volts / step) * step
        return {"pressure_kpa": voltage / 5 * c.pressure_sensor_span_kpa,
                "pressure_voltage_v": voltage,
                "temperature_c": c.ambient_temperature_c + self._daq_rng.gauss(0, c.temperature_noise_c)}

    def camera(self):
        c = self.config
        expected = color_rgb(self._fraction_a, c)
        frames = [[min(255, max(0, v + self._camera_rng.gauss(0, c.camera_noise_rgb))) for v in expected]
                  for _ in range(c.camera_replicates)]
        mean = [sum(frame[i] for frame in frames) / len(frames) for i in range(3)]
        return {"rgb": mean, "frames": len(frames), "time_s": round(self.time_s, 6),
                "status": "simulated_roi_mean"}

    def snapshot(self):
        # Passive polling consumes no RNG: browser observation cannot change experiments.
        return {"time_s": round(self.time_s, 6), "commanded_ul_min": self.commanded.copy(),
                "remaining_ul": self.remaining.copy(), "daq": self._cached_daq.copy(),
                "interlock": self.interlock, "clog_factor": self.clog_factor,
                "stopped": not any(self.commanded), "mode": "simulation"}

    def display_truth(self):
        """Dashboard diagnostics only. Do not expose this through agent tools."""
        return {"actual_ul_min": self.actual.copy(), "fraction_a": self._fraction_a,
                "rgb": color_rgb(self._fraction_a, self.config), "pressure_kpa": self._pressure}

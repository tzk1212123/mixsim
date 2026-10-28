"""Immutable, validated assumptions. SI units inside physics; explicit units at APIs."""

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from .syringes import get_syringe


@dataclass(frozen=True)
class RigConfig:
    # Explicit manual-table entry; selecting a profile fixes its diameter and rates.
    syringe_profile: str = "hsw_norm_ject_10ml"
    # Water at 25 C: rounded from the NIST reference; see docs/MODEL.md.
    viscosity_pa_s: float = 0.00089
    ambient_temperature_c: float = 25.0
    # Geometry and all noise/calibration values below are assumptions, not bench data.
    tube_length_m: float = 0.5
    tube_radius_m: float = 0.00015
    transport_volume_ul: float = 35.34291735288517
    mixing_volume_ul: float = 30.0
    pump_tau_s: float = 1.0
    pressure_tau_s: float = 0.5
    integration_step_s: float = 0.1
    syringe_capacity_ul: float = 10000.0  # Initial fill per pump, <= profile capacity.
    max_flow_ul_min: float = 1000.0
    max_total_flow_ul_min: float = 1500.0
    pressure_trip_kpa: float = 60.0
    pressure_reset_kpa: float = 5.0
    pressure_sensor_span_kpa: float = 100.0
    pressure_noise_kpa: float = 0.08
    temperature_noise_c: float = 0.03
    camera_noise_rgb: float = 0.6
    calibration_sd: float = 0.02
    camera_replicates: int = 5
    # Synthetic optical-density vectors, representing amber and blue stock dyes.
    dye_a_od: tuple[float, float, float] = (0.05, 0.45, 1.4)
    dye_b_od: tuple[float, float, float] = (1.5, 0.4, 0.08)
    white_rgb: tuple[float, float, float] = (245.0, 245.0, 245.0)

    def __post_init__(self):
        syringe = self.syringe
        for name, value in asdict(self).items():
            if name == "syringe_profile":
                continue
            values = value if isinstance(value, (list, tuple)) else (value,)
            if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in values):
                raise ValueError(f"{name} must contain finite numbers")
        positive = ("viscosity_pa_s", "tube_length_m", "tube_radius_m", "transport_volume_ul",
                    "mixing_volume_ul", "pump_tau_s", "pressure_tau_s", "integration_step_s",
                    "syringe_capacity_ul", "max_flow_ul_min", "max_total_flow_ul_min",
                    "pressure_trip_kpa", "pressure_reset_kpa", "pressure_sensor_span_kpa")
        if any(getattr(self, name) <= 0 for name in positive):
            raise ValueError("Physical dimensions, time constants and limits must be positive")
        if not 0 < self.integration_step_s <= 0.5:
            raise ValueError("integration_step_s must be in (0, 0.5]")
        if not 0 < self.pressure_reset_kpa < self.pressure_trip_kpa < self.pressure_sensor_span_kpa:
            raise ValueError("Require reset < trip < pressure sensor span")
        if self.syringe_capacity_ul > syringe.capacity_ml * 1000:
            raise ValueError("Initial fill exceeds selected syringe capacity")
        if not syringe.min_flow_ul_min <= self.max_flow_ul_min <= syringe.max_flow_ul_min:
            raise ValueError("Project pump limit must be within the selected syringe's device flow range")
        if self.max_total_flow_ul_min > 2 * self.max_flow_ul_min:
            raise ValueError("Total limit cannot exceed two pump limits")
        if self.max_total_flow_ul_min < syringe.min_flow_ul_min:
            raise ValueError("Total limit must permit at least one pump's minimum nonzero flow")
        for name in ("pressure_noise_kpa", "temperature_noise_c", "camera_noise_rgb", "calibration_sd"):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} must be nonnegative")
        if not 0 <= self.calibration_sd <= 0.1:
            raise ValueError("calibration_sd must be in [0, 0.1]")
        if type(self.camera_replicates) is not int or not 1 <= self.camera_replicates <= 100:
            raise ValueError("camera_replicates must be an integer in [1, 100]")
        if any(len(getattr(self, name)) != 3 for name in ("dye_a_od", "dye_b_od", "white_rgb")):
            raise ValueError("Optical vectors must have three channels")
        if any(v < 0 for v in (*self.dye_a_od, *self.dye_b_od)):
            raise ValueError("Optical densities must be nonnegative")
        if any(not 0 < v <= 255 for v in self.white_rgb):
            raise ValueError("white_rgb channels must be in (0, 255]")
        if self.dye_a_od == self.dye_b_od:
            raise ValueError("Dye stocks must be optically distinguishable")

    @property
    def syringe(self):
        return get_syringe(self.syringe_profile)

    def to_dict(self):
        return asdict(self)

    @classmethod
    def load(cls, path: str | Path):
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        for name in ("dye_a_od", "dye_b_od", "white_rgb"):
            if name in data:
                data[name] = tuple(data[name])
        return cls(**data)


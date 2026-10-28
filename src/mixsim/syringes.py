"""Selected NE-1000 syringe examples from manual section 12.7, printed page 50.

These are representative table entries, not a complete syringe database or a
measurement of the actual bench syringes. Both simulated pumps share a profile.
"""

from dataclasses import asdict, dataclass
from decimal import Decimal
from types import MappingProxyType


@dataclass(frozen=True)
class SyringeSpec:
    manufacturer: str
    capacity_ml: float
    inside_diameter_mm: float
    min_rate_ul_hr: float
    max_rate_ml_hr: float

    @property
    def min_flow_ul_min(self):
        # Convert the manual's decimal value before rounding to a binary float.
        # Otherwise 6.876 / 60 lands above the valid literal boundary 0.1146.
        return float(Decimal(str(self.min_rate_ul_hr)) / 60)

    @property
    def max_flow_ul_min(self):
        return self.max_rate_ml_hr * 1000 / 60

    def to_dict(self):
        return asdict(self) | {
            "min_nonzero_flow_ul_min": self.min_flow_ul_min,
            "max_flow_ul_min": self.max_flow_ul_min,
            "source": "NE-1000 Syringe Pump User Manual, V3.923, section 12.7, printed page 50",
        }


SYRINGE_PROFILES = MappingProxyType({
    "hsw_norm_ject_10ml": SyringeSpec("HSW Norm-Ject", 10.0, 15.9, 8.349, 607.6),
    "bd_10ml": SyringeSpec("B-D", 10.0, 14.43, 6.876, 500.4),
})


def get_syringe(profile: str) -> SyringeSpec:
    if not isinstance(profile, str) or profile not in SYRINGE_PROFILES:
        raise ValueError(f"Unknown syringe_profile; choose one of {', '.join(SYRINGE_PROFILES)}")
    return SYRINGE_PROFILES[profile]

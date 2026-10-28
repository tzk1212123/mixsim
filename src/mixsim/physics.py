"""Reduced-order flow and optics; no CFD or calibrated camera claim."""

import math
from .config import RigConfig


def pressure_kpa(flow_ul_min: float, config: RigConfig, clog_factor: float = 1.0) -> float:
    """Hagen–Poiseuille: delta P = 8 mu L Q / (pi r**4); Q in m3/s."""
    q_m3_s = flow_ul_min * 1e-9 / 60
    return 8 * config.viscosity_pa_s * config.tube_length_m * q_m3_s / (math.pi * config.tube_radius_m**4) / 1000 * clog_factor


def color_rgb(fraction_a: float, config: RigConfig) -> list[float]:
    """Beer–Lambert mixture in synthetic camera channels, OD uses base 10."""
    return [w * 10 ** (-(fraction_a * a + (1 - fraction_a) * b))
            for w, a, b in zip(config.white_rgb, config.dye_a_od, config.dye_b_od)]


def color_error(rgb, target) -> float:
    """RGB RMSE in digital numbers (0..255). Not perceptual Delta E."""
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(rgb, target)) / 3)


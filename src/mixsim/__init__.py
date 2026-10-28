"""MixSim: an MHS-style simulation, not an official MHS implementation."""

from .config import RigConfig
from .rig import Rig, RigError

__all__ = ["Rig", "RigConfig", "RigError"]
__version__ = "0.1.1"


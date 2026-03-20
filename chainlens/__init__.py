"""ChainLens - EVM blockchain monitoring and analytics agent."""

__version__ = "0.1.0"
__author__ = "Kynareth01"

from chainlens.monitor import BlockMonitor
from chainlens.config import ChainLensConfig

__all__ = ["BlockMonitor", "ChainLensConfig"]

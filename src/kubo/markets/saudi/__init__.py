"""Saudi Exchange adapter.

Main Market equities are active by default.  Nomu is represented explicitly
but is disabled unless a caller opts into a separate, tested segment policy.
"""

from .benchmarks import SaudiBenchmarkRegistry
from .calendar import SaudiSession, SaudiTradingCalendar
from .config import SAUDI_MARKET
from .identity import SaudiSecurityMaster, SaudiSecurityRecord
from .sources import SAUDI_SOURCES

__all__ = [
    "SAUDI_MARKET",
    "SAUDI_SOURCES",
    "SaudiBenchmarkRegistry",
    "SaudiSecurityMaster",
    "SaudiSecurityRecord",
    "SaudiSession",
    "SaudiTradingCalendar",
]

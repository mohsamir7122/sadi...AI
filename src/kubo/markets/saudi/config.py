"""Saudi Exchange market configuration and dated official references."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, time

from ..base import MarketConfig


MAIN_MARKET = "MAIN"
NOMU = "NOMU"
SAR = "SAR"
RIYADH_TZ = "Asia/Riyadh"
TASI = "TASI"
MT30 = "MT30"
NOMUC = "NomuC"


@dataclass(frozen=True)
class SaudiMarketConfig(MarketConfig):
    official_exchange_url: str = "https://www.saudiexchange.sa"
    trading_cycle_url: str = (
        "https://www.saudiexchange.sa/wps/portal/saudiexchange/"
        "rules-guidance/capital-market-overview/trading-cycle-and-times"
    )
    ereference_url: str = (
        "https://www.saudiexchange.sa/wps/portal/saudiexchange/"
        "trading/market-services/market-information-services/ereference-data?locale=en"
    )
    corporate_actions_url: str = (
        "https://www.saudiexchange.sa/wps/portal/saudiexchange/"
        "newsandreports/issuer-financial-calendars/corporate-actions"
    )
    sessions_effective_from: date = date(2026, 1, 1)
    opening_auction_start: time = time(9, 30)
    opening_auction_end: time = time(10, 0)
    continuous_start: time = time(10, 0)
    continuous_end: time = time(15, 0)
    closing_auction_end: time = time(15, 10)
    trade_at_last_end: time = time(15, 20)


SAUDI_MARKET = SaudiMarketConfig(
    market_id="SAUDI_EXCHANGE",
    display_name="Saudi Exchange",
    currency=SAR,
    timezone=RIYADH_TZ,
    primary_benchmark=TASI,
    default_segment=MAIN_MARKET,
)

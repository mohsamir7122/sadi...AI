"""Saudi source authority registry.

All sources start as DEFINED_ONLY.  Admission is a separate reviewed action;
having a URL in this file never claims access, freshness, or redistribution
rights.
"""
from __future__ import annotations

from ..base import MarketSource


SAUDI_SOURCES = (
    MarketSource(
        "saudi_exchange_ereference",
        "Saudi Exchange eReference",
        "https://www.saudiexchange.sa/wps/portal/saudiexchange/trading/market-services/market-information-services/ereference-data?locale=en",
        1,
        "saudi_exchange",
        "REVIEWED_ACCESS_REQUIRED",
        "UNKNOWN",
        "LICENSE_REVIEW_REQUIRED",
    ),
    MarketSource(
        "saudi_exchange_announcements",
        "Saudi Exchange issuer announcements",
        "https://www.saudiexchange.sa/wps/portal/saudiexchange/newsandreports/issuer-news/issuer-announcements",
        1,
        "saudi_exchange",
        "PUBLIC_OFFICIAL_WEB",
        "DELAYED",
        "PUBLIC_RESEARCH_REVIEW_REQUIRED",
    ),
    MarketSource(
        "cma_rules",
        "Capital Market Authority",
        "https://cma.gov.sa/en/RulesRegulations/Regulations/Pages/default.aspx",
        1,
        "cma",
        "PUBLIC_OFFICIAL_WEB",
        "UNKNOWN",
        "PUBLIC_RESEARCH_REVIEW_REQUIRED",
    ),
)

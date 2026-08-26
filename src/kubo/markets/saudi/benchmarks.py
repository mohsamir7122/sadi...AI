"""Named Saudi benchmarks; no silent benchmark substitution."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .config import MT30, NOMUC, SAR, TASI


@dataclass(frozen=True)
class SaudiBenchmark:
    code: str
    name: str
    scope: str
    currency: str
    effective_from: date
    effective_to: date | None = None

    def active_on(self, on: date) -> bool:
        return on >= self.effective_from and (self.effective_to is None or on <= self.effective_to)


class SaudiBenchmarkRegistry:
    def __init__(self, benchmarks: tuple[SaudiBenchmark, ...] | None = None):
        self._benchmarks = benchmarks or (
            SaudiBenchmark(TASI, "Tadawul All Share Index", "BROAD_MARKET", SAR, date(2026, 1, 1)),
            SaudiBenchmark(MT30, "MSCI Tadawul 30", "LARGE_CAP", SAR, date(2026, 1, 1)),
            SaudiBenchmark(NOMUC, "Nomu Composite Index", "NOMU", SAR, date(2026, 1, 1)),
        )

    def get(self, code: str, *, as_of: date) -> SaudiBenchmark:
        matches = [item for item in self._benchmarks if item.code == code and item.active_on(as_of)]
        if len(matches) != 1:
            raise LookupError(f"benchmark {code!r} is not uniquely active on {as_of}")
        return matches[0]

    def require_sector_benchmark(self, *, sector: str, code: str, as_of: date) -> SaudiBenchmark:
        benchmark = self.get(code, as_of=as_of)
        if benchmark.scope != "SECTOR" or not sector.strip():
            raise ValueError("sector analysis requires an explicit sector benchmark")
        return benchmark

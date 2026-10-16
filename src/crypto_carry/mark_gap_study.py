"""Observe approved mark-gap risk without changing the economic engine."""

from dataclasses import asdict
from time import monotonic

from .config import iso
from .data.mark_gaps import APPROVED_MINUTES, MINUTE, official_anchor
from .margin import margin_state
from .strategy import Backtest


def gap_windows():
    groups = {}
    for symbol, t in sorted(APPROVED_MINUTES):
        anchor = official_anchor(symbol, t)
        groups[symbol, anchor] = max(t, groups.get((symbol, anchor), t))
    return [(s, anchor, last) for (s, anchor), last in sorted(groups.items())]


class GapAuditedBacktest(Backtest):
    """Observe the existing risk predicate without changing orders or balances."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mark_gap_checks = []
        self._gap_windows = gap_windows()
        self._progress_at = monotonic()

    def process(self, time_ns, records, native):
        super().process(time_ns, records, native)
        if monotonic() - self._progress_at >= 30:
            self._progress_at = monotonic()
            fraction = max(0, min(1, (self.now - self.start) / (self.end - self.start)))
            print(
                f"[{self.config.mark_gap_method}/{self.strategy}] {fraction:.1%} "
                f"| UTC {iso(self.now)} | fills {len(self.fills)}",
                flush=True,
            )

    def _risk(self, symbol, periodic=False):
        window = next(
            (
                w
                for w in self._gap_windows
                if w[0] == symbol and w[1] + MINUTE <= self.now <= w[2] + 2 * MINUTE
            ),
            None,
        )
        if window is None:
            return super()._risk(symbol, periodic)
        mark = self.marks.get(symbol)
        p, pair = self.ledger.positions[symbol], self.pairs[symbol]
        row = dict(
            time_ns=self.now,
            timestamp_utc=iso(self.now),
            symbol=symbol,
            strategy=self.strategy,
            method=self.config.mark_gap_method,
            gap_anchor=window[1],
            gap_last=window[2],
            periodic=periodic,
            state_before=pair.state.value,
            **asdict(p),
            pending_orders_before=[o.order_id for o in self._pending(symbol)],
            mark_open_time=mark.open_time if mark else None,
            mark_available_at=mark.available_at if mark else None,
            mark_close=mark.close if mark else None,
            mark_source=mark.source_file if mark else None,
            estimation_method=mark.estimation_method if mark else None,
            stage="anchor"
            if mark and mark.open_time == window[1]
            else "estimated"
            if mark and (symbol, mark.open_time) in APPROVED_MINUTES
            else "recovery",
            equity_before_risk=self.equity(),
            margin_exit_ratio=self.config.margin_exit_ratio,
            liquidation_distance=self.config.liquidation_distance,
            risk_applicable=bool(p.spot > 0 or p.short > 0 or self._pending(symbol)),
        )
        rule = self._rule(symbol, "futures")
        row.update(
            dict(
                balance=None,
                maintenance=None,
                liquidation_price=None,
                ratio=None,
                distance=None,
                liquidate=False,
                preventive=False,
            )
        )
        if p.short > 0 and mark and rule:
            try:
                row.update(
                    margin_state(p.short, p.average, p.collateral, mark.close, rule, self.config)
                )
            except ValueError as exc:
                # The observer records the failure; the parent owns the halt.
                row["margin_error"] = str(exc)
        offset = len(self.risk_events)
        super()._risk(symbol, periodic)
        row.update(
            state_after=pair.state.value,
            risk_events=[dict(e) for e in self.risk_events[offset:]],
            pending_orders_after=[o.order_id for o in self._pending(symbol)],
            equity_after_risk=self.equity(),
        )
        self.mark_gap_checks.append(row)


def compare_records(left: list[dict], right: list[dict]) -> dict:
    """Ignore run identity, retaining all economic and decision fields."""
    ignored = {"run_id", "units", "data_kind"}

    def clean(rows):
        return [{k: v for k, v in row.items() if k not in ignored} for row in rows]

    a, b = clean(left), clean(right)
    changed = sum(x != y for x, y in zip(a, b)) + abs(len(a) - len(b))
    return dict(
        identical=a == b, changed_rows=changed, primary_rows=len(a), sensitivity_rows=len(b)
    )

"""Opt-in block-5 feed adapter and read-only observations at intervention times.

The underlying state machine, rule book, funding, fills and ledger are unchanged.
All intervention state uses the existing inspectable checkpoint encoding.
"""

import hashlib
import json
from bisect import bisect_right
from copy import deepcopy
from dataclasses import asdict, replace
from decimal import Decimal as D

from .costs import cycle_cost
from .data.stress_counterfactual import MINUTE, compile_shock, counterfactual_bar, shock_bar
from .events import event_key
from .margin import margin_state
from .mark_gap_study import GapAuditedBacktest
from .models import MinuteBar


def plain_bar(bar):
    return {k: str(v) if isinstance(v, D) else v for k, v in asdict(bar).items()}


def record_hash(row):
    return hashlib.sha256(json.dumps(row, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False).encode()).hexdigest()


class ScenarioBacktest(GapAuditedBacktest):
    def __init__(self, *args, scenario=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.scenario = deepcopy(scenario or {"id": "OFF", "kind": "off"})
        kind = self.scenario["kind"]
        if kind not in {"off", "shock", "counterfactual"}:
            raise ValueError("Unknown scenario kind")
        if kind != "off" and self.config.execution_model != "next_minute_vwap":
            raise ValueError("Scenario adapter requires closed one-minute execution")
        self.scenario_factors = compile_shock(
            self.scenario["episodes"], self.scenario["magnitudes"]) if kind == "shock" else {}
        self.original_spot = {}
        self.anchor_verified = False
        self.interventions = []
        self.scenario_observations = []
        self.opportunity_observations = []
        self.phase_before_fills = None
        self.phase_after_fills = None
        self.scenario_intervals = self._observation_intervals()
        self.scenario_starts = [a for a, _ in self.scenario_intervals]

    def _observation_intervals(self):
        if self.scenario["kind"] == "shock":
            points = sorted({u for (_, u), f in self.scenario_factors.items() if f != 1})
            spans = [(u, u + 3 * MINUTE) for u in points]
        elif self.scenario["kind"] == "counterfactual":
            spans = [(self.scenario["start"], self.scenario["end"] + 2 * MINUTE)]
        else:
            return []
        merged = []
        for start, end in spans:
            if merged and start <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], end))
            else:
                merged.append((start, end))
        return merged

    def factor_at(self, symbol, time_ns):
        opening = (time_ns // MINUTE - 1) * MINUTE
        return self.scenario_factors.get((symbol, opening), D(1))

    def _observe_at(self, time_ns):
        i = bisect_right(self.scenario_starts, time_ns) - 1
        return i >= 0 and time_ns <= self.scenario_intervals[i][1]

    def _journal(self, original, changed, *, future=None, factor=None):
        old = plain_bar(original) if original else None
        new = plain_bar(changed)
        source = plain_bar(future) if future else old
        self.interventions.append(dict(
            scenario=self.scenario["id"], kind=self.scenario["kind"],
            symbol=changed.symbol, open_time=changed.open_time,
            available_at=changed.available_at, original=old, modified=new,
            original_record_sha256=record_hash(old), source_record=source,
            source_record_sha256=record_hash(source), modified_record_sha256=record_hash(new),
            factor=factor, units="OHLC,VWAP:USDT/base; base:asset; quote:USDT; time:UTC ns",
            formula="spot_OHLC_quote_times_factor" if factor is not None
                    else "fixed_anchor_times_future; approved_prior_spot_median_volume"))

    def _adapt(self, time_ns, records):
        kind = self.scenario["kind"]
        if kind == "off":
            return records
        bars = {(r.symbol, r.market): r for r in records if isinstance(r, MinuteBar)}
        for bar in bars.values():
            if bar.available_at != time_ns or bar.end_time != time_ns:
                raise ValueError("Scenario received a noncausal minute")
            if bar.market == "spot" and bar.base_volume > 0:
                self.original_spot[bar.symbol] = bar
        if kind == "shock":
            changed = []
            for record in records:
                if isinstance(record, MinuteBar) and record.market == "spot":
                    factor = self.scenario_factors.get((record.symbol, record.open_time), D(1))
                    adjusted = shock_bar(record, factor, self.scenario["id"])
                    if factor != 1:
                        self._journal(record, adjusted, factor=factor)
                    record = adjusted
                changed.append(record)
            # Valuation advances the imposed factor clock, never source freshness.
            # This is not a new market event and cannot fill an execution window.
            for symbol, original in self.original_spot.items():
                current = bars.get((symbol, "spot"))
                if current is None or current.base_volume == 0:
                    factor = self.factor_at(symbol, time_ns)
                    self.trades[symbol, "spot"] = replace(
                        original, open=original.open * factor, high=original.high * factor,
                        low=original.low * factor, close=original.close * factor,
                        quote_volume=original.quote_volume * factor,
                        source_file=original.source_file if factor == 1 else
                        f"scenario:{self.scenario['id']}:stale_valuation|{original.source_file}")
            return changed
        lower, upper = self.scenario["start"], self.scenario["end"]
        if time_ns == lower:
            for symbol, anchor in self.scenario["anchors"].items():
                for market in ("spot", "futures"):
                    bar = bars.get((symbol, market))
                    if (bar is None or bar.open_time != lower - MINUTE
                            or bar.close != anchor[market] or bar.base_volume <= 0):
                        raise ValueError("Counterfactual anchor differs from preclosure source")
            self.anchor_verified = True
        if time_ns % MINUTE or not lower <= time_ns - MINUTE < upper:
            return records
        if not self.anchor_verified:
            raise ValueError("Counterfactual anchor was not available before synthesis")
        opening = time_ns - MINUTE
        changed = [r for r in records if not (
            isinstance(r, MinuteBar) and r.market == "spot" and r.symbol in self.scenario["anchors"])]
        for symbol, anchor in self.scenario["anchors"].items():
            future = bars.get((symbol, "futures"))
            if future is None or future.open_time != opening:
                raise ValueError("Missing counterfactual future source minute")
            volume, count = self.scenario["volumes"][symbol, opening]
            bar = counterfactual_bar(future, anchor["spot"], anchor["futures"],
                                     volume, count, self.scenario["id"])
            self._journal(bars.get((symbol, "spot")), bar, future=future)
            changed.append(bar)
        return sorted(changed, key=event_key)

    def _snapshot(self):
        assets = {}
        for symbol, p in self.ledger.positions.items():
            spot = self.trades.get((symbol, "spot"))
            original = self.original_spot.get(symbol)
            mark = self.marks.get(symbol)
            rule = self._rule(symbol, "futures")
            margin, margin_error = None, None
            if p.short > 0 and mark and rule:
                try:
                    margin = margin_state(p.short, p.average, p.collateral, mark.close, rule,
                                          self.config)
                except ValueError as exc:
                    # Observation cannot replace the engine's own coverage halt.
                    margin_error = str(exc)
            assets[symbol] = dict(
                **asdict(p), state=self.pairs[symbol].state.value,
                spot_price=spot.price if spot else None,
                spot_source_available_at=spot.available_at if spot else None,
                spot_source=spot.source_file if spot else None,
                original_spot_price=original.price if original else None,
                original_spot_available_at=original.available_at if original else None,
                original_spot_source=original.source_file if original else None,
                original_spot_record_sha256=record_hash(plain_bar(original)) if original else None,
                factor=self.factor_at(symbol, self.now),
                mark=mark.close if mark else None, margin=margin, margin_error=margin_error,
                reservation=self.reservations.get(symbol, D(0)),
                pending_orders=[asdict(o) for o in self._pending(symbol)])
        return dict(time_ns=self.now, equity=self.equity(), free_spot=self.ledger.free_spot,
                    free_futures=self.ledger.free_futures, debt=self.ledger.debt,
                    reservations=sum(self.reservations.values(), D(0)), assets=assets)

    def _fill_minute_windows(self, bars):
        observed = self._observe_at(self.now) and self.now >= self.start
        # Phase 2: new market data and funding are present, quantities are still
        # those preceding simultaneous fills. No risk action is introduced here.
        if observed:
            self.phase_before_fills = self._snapshot()
        super()._fill_minute_windows(bars)
        if observed:
            self.phase_after_fills = self._snapshot()

    def _opportunity(self):
        offset = len(self.opportunities)
        super()._opportunity()
        if not self._observe_at(self.now):
            return
        for result in self.opportunities[offset:]:
            symbol = result["symbol"]
            spot, future = self._signal_prices(symbol)
            fc = self.forecasts.get(symbol)
            spot_rule, future_rule = self._rule(symbol, "spot"), self._rule(symbol, "futures")
            self.opportunity_observations.append(dict(
                result, forecast=asdict(fc) if fc else None,
                spot_bar=plain_bar(spot) if spot else None,
                future_bar=plain_bar(future) if future else None,
                mark_present=symbol in self.marks, bad_symbol=symbol in self.bad_symbols,
                rules_present=spot_rule is not None and future_rule is not None,
                operational=bool(spot_rule and future_rule
                                 and spot_rule.operational and future_rule.operational),
                fresh=self._fresh(symbol),
                selection_cost=cycle_cost(spot_rule, future_rule, self.config)
                    if spot_rule and future_rule else None,
                position_independent=True))

    def process(self, time_ns, records, native):
        if self.stopped_at is not None or time_ns >= self.end:
            return
        observed = self._observe_at(time_ns) and time_ns >= self.start
        before = self._snapshot() if observed else None
        self.phase_before_fills = self.phase_after_fills = None
        prepared = self._adapt(time_ns, records)
        super().process(time_ns, prepared, native)
        if observed:
            self.scenario_observations.append(dict(time_ns=time_ns, before=before,
                                                   before_fills=self.phase_before_fills,
                                                   after_fills=self.phase_after_fills,
                                                   after=self._snapshot()))

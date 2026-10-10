"""Asset accounts and cycle boundaries from persisted movements, never a replay."""

from collections import defaultdict
from dataclasses import asdict, dataclass
from decimal import Decimal as D

from .common import COMPONENTS, close, number


@dataclass
class Account:
    spot: D = D(0)
    short: D = D(0)
    average: D = D(0)
    spot_cost: D = D(0)
    realized_spot: D = D(0)
    realized_futures: D = D(0)
    funding: D = D(0)
    fees: D = D(0)
    liquidation_fees: D = D(0)
    collateral: D = D(0)
    asset_cash: D = D(0)

    def apply(self, row):
        """Check actual proportional accounting and retain all original cash costs."""
        kind = row["kind"]
        if kind == "transfer":
            return
        fee = number(row.get("fee"), optional=True)
        charge = number(row.get("liquidation_fee"), optional=True)
        realized = D(0)
        if kind == "funding":
            if "short" in row:
                close(row["short"], self.short, "funding position before simultaneous fills")
            self.funding += number(row["funding"])
        else:
            q, price = number(row["quantity"]), number(row["price"])
            if q <= 0 or price <= 0:
                raise ValueError("Nonpositive fill")
            if kind == "spot_buy":
                net = q - number(row["base_fee_quantity"])
                close(number(row["base_fee_quantity"]) * price, fee, "base fee valued once")
                self.spot += net
                self.spot_cost += net * price
            elif kind == "spot_sell":
                if q > self.spot:
                    raise ValueError("Sell exceeds spot")
                allocated = self.spot_cost * q / self.spot
                realized = q * price - allocated
                self.spot -= q
                self.spot_cost -= allocated
                self.realized_spot += realized
            elif kind == "futures_sell":
                self.average = (self.short * self.average + q * price) / (self.short + q)
                self.short += q
            elif kind == "futures_buy":
                if q > self.short:
                    raise ValueError("Buy exceeds short")
                realized = q * (self.average - price)
                self.short -= q
                self.realized_futures += realized
                if not self.short:
                    self.average = D(0)
            else:
                raise ValueError(f"Unknown ledger kind {kind}")
            if row.get("pnl") is not None:
                close(realized, row["pnl"], "ledger realized P&L")
        self.fees += fee
        self.liquidation_fees += charge
        if row.get("collateral") is not None:
            self.collateral = number(row["collateral"])
        for field in ("spot", "short", "average"):
            if row.get(field) is not None:
                close(getattr(self, field), row[field], f"ledger post {field}")


def components(account, spot_price, mark):
    if account.spot and spot_price is None or account.short and mark is None:
        raise ValueError("Missing valuation price for nonzero inventory")
    values = dict(
        spot_realized_pnl_usdt=account.realized_spot,
        spot_unrealized_pnl_usdt=account.spot * number(spot_price, optional=True)
        - account.spot_cost,
        futures_realized_pnl_usdt=account.realized_futures,
        futures_unrealized_pnl_usdt=account.short * (account.average - number(mark, optional=True)),
        funding_usdt=account.funding,
        fees_usdt=-account.fees,
        liquidation_fees_usdt=-account.liquidation_fees,
    )
    values["net_pnl_usdt"] = sum((values[k] for k in COMPONENTS), D(0))
    return values


def account_history(rows, capital, symbols):
    accounts = {s: Account() for s in symbols}
    history = {s: [(-1, -1, asdict(accounts[s]))] for s in symbols}
    prior_cash, seen, previous_time = number(capital), set(), -1
    for ordinal, row in enumerate(rows):
        t, identity = int(row["time_ns"]), row["event_id"]
        if identity in seen or t < previous_time:
            raise ValueError("Duplicate or unordered ledger event")
        seen.add(identity)
        previous_time = t
        account = accounts[row["symbol"]]
        account.apply(row)
        cash = number(row["free_spot"]) + number(row["free_futures"]) - number(row["debt"])
        account.asset_cash += cash - prior_cash
        prior_cash = cash
        history[row["symbol"]].append((t, ordinal, asdict(account)))
    return history


def cycle_catalog(events, end):
    """Same original entry/open/first terminal semantics as E3 cycle_rows()."""
    grouped = defaultdict(list)
    for ordinal, row in enumerate(events):
        if row.get("cycle_id"):
            grouped[row["symbol"], row["cycle_id"]].append((ordinal, row))
    result = []
    for (symbol, cycle), rows in grouped.items():
        entries = [
            (i, r) for i, r in rows if r["kind"] == "transition" and r.get("cause") == "entry"
        ]
        if len(entries) != 1:
            raise ValueError(f"Cycle must have one entry: {cycle}")
        opened = [
            int(r["time_ns"])
            for _, r in rows
            if r["kind"] == "transition" and r.get("cause") == "opening_complete"
        ]
        closed = [
            int(r["time_ns"])
            for _, r in rows
            if r["kind"] == "transition"
            and r.get("cause") in {"ordinary_close_complete", "unwind_complete"}
            and r.get("state") in {"FLAT", "COOLDOWN"}
        ]
        entry = int(entries[0][1]["time_ns"])
        closure = min(closed) if closed else None
        result.append(
            dict(
                symbol=symbol,
                cycle_id=cycle,
                entry_ns=entry,
                opened_ns=min(opened) if opened else None,
                closed_ns=closure,
                complete=bool(opened and closed),
                failed=bool(closed and not opened),
                still_open_at_end=not closed,
                entry_risk_row=entries[0][0],
                end_ns=closure if closure is not None else end - 1,
            )
        )
    return sorted(result, key=lambda r: (r["entry_ns"], r["symbol"]))


def validate_entry_timing(cycles, ledger):
    """Entry snapshots are post-event: the frozen next-minute contract forbids fills here."""
    entries = {(c["symbol"], c["entry_ns"]): c["cycle_id"] for c in cycles}
    for row in ledger:
        key = row["symbol"], int(row["time_ns"])
        economic = row["kind"] in {"spot_buy", "spot_sell", "futures_buy", "futures_sell"} or any(
            number(row.get(field), optional=True)
            for field in ("pnl", "funding", "fee", "liquidation_fee")
        )
        if key in entries and economic:
            raise ValueError(
                f"Simultaneous economic movement at cycle entry {entries[key]}; "
                "requires an explicit pre/post entry boundary, outside this frozen next_minute_vwap contract"
            )


def segment_changes(points):
    output = []
    for before, after in zip(points, points[1:]):
        if after["time_ns"] <= before["time_ns"]:
            raise ValueError("Non-increasing attribution boundaries")
        delta = {key: value - before["values"][key] for key, value in after["values"].items()}
        output.append(
            dict(
                start_ns=before["time_ns"],
                time_ns=after["time_ns"],
                category=before["category_after"],
                cycle_id=before["cycle_after"],
                **delta,
            )
        )
    return output

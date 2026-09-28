"""Read-only cash/inventory arithmetic and linkage to persisted daily/state records."""

from bisect import bisect_left, bisect_right
from dataclasses import asdict
from decimal import Decimal as D

from scripts.cost_capacity_audit import same
from scripts.return_capital.accounting import Account
from scripts.return_capital.common import number


def audit_ledger(config, rows, daily, positions):
    accounts = {s: Account() for s in config.symbols}
    histories = {s: [(-1, asdict(a))] for s, a in accounts.items()}
    spot_cash, futures_cash, debt = config.capital, D(0), D(0)
    cash_history = [(-1, spot_cash, futures_cash, debt)]
    seen, previous = set(), -1

    def receive(amount, destination):
        nonlocal spot_cash, futures_cash, debt
        repaid = min(amount, debt)
        debt -= repaid
        if destination == "spot":
            spot_cash += amount-repaid
        else:
            futures_cash += amount-repaid

    for row in rows:
        t, kind, symbol = int(row["time_ns"]), row["kind"], row["symbol"]
        if row["event_id"] in seen or t < previous:
            raise ValueError("Duplicate or unordered ledger event")
        seen.add(row["event_id"])
        previous = t
        before_spot, before_future, before_debt = spot_cash, futures_cash, debt
        def n(field):
            return number(row.get(field), optional=True)
        if kind == "transfer":
            amount = n("transfer")
            if not 0 < amount <= spot_cash:
                raise ValueError("Invalid cash transfer")
            spot_cash -= amount
            futures_cash += amount
            same(n("fee"), 0, "Transfer fee")
            same(n("pnl"), 0, "Transfer P&L")
        else:
            account = accounts[symbol]
            before_collateral = account.collateral
            expected_collateral = before_collateral
            q, price, fee = n("quantity"), n("price"), n("fee")
            if kind == "spot_buy":
                gross = q*price
                transfer = max(D(0), gross-spot_cash)
                if debt or gross > spot_cash+futures_cash:
                    raise ValueError("Unaffordable spot ledger fill")
                spot_cash += transfer-gross
                futures_cash -= transfer
                same(n("transfer_futures_to_spot"), transfer, "Purchase transfer")
                same(n("spot_cost"), gross, "Gross purchase cash")
            elif kind == "spot_sell":
                receive(q*price-fee, "spot")
                same(n("spot_proceeds"), q*price, "Gross sale cash")
            elif kind == "futures_sell":
                if n("open_loss") < 0:
                    raise ValueError("Negative original opening loss buffer")
                collateral_added = q*price/config.leverage+n("open_loss")
                required = collateral_added+fee
                if debt or required > spot_cash+futures_cash:
                    raise ValueError("Unaffordable futures ledger fill")
                from_future = min(futures_cash, required)
                futures_cash -= from_future
                spot_cash -= required-from_future
                expected_collateral += collateral_added
            elif kind == "futures_buy":
                if not 0 < q <= account.short:
                    raise ValueError("Futures close exceeds original inventory")
                released = before_collateral*q/account.short
                net = q*(account.average-price)-fee-n("liquidation_fee")
                expected_collateral -= released
                if net >= 0:
                    receive(released+net, "futures")
                else:
                    obligation = -net
                    paid = min(futures_cash, obligation)
                    futures_cash -= paid
                    obligation -= paid
                    paid = min(spot_cash, obligation)
                    spot_cash -= paid
                    obligation -= paid
                    from_released = min(released, obligation)
                    debt += obligation-from_released
                    receive(released-from_released, "futures")
            elif kind == "funding":
                amount = n("funding")
                same(n("amount_usdt"), amount, "Funding amount")
                if amount >= 0:
                    receive(amount, "futures")
                else:
                    obligation = -amount
                    paid = min(futures_cash, obligation)
                    futures_cash -= paid
                    obligation -= paid
                    paid = min(before_collateral, obligation)
                    expected_collateral -= paid
                    obligation -= paid
                    paid = min(spot_cash, obligation)
                    spot_cash -= paid
                    debt += obligation-paid
            else:
                raise ValueError("Unknown ledger movement "+kind)
            same(n("collateral_change"), expected_collateral-before_collateral, "Collateral movement")
            same(n("collateral"), expected_collateral, "Collateral stock")
            account.apply(row)
            histories[symbol].append((t, asdict(account)))
        for field, value in (("free_spot", spot_cash), ("free_futures", futures_cash), ("debt", debt)):
            same(row[field], value, "Ledger balance "+field)
        if kind not in {"funding", "transfer"}:
            for field, value in (("cash_spot_change", spot_cash-before_spot),
                                 ("cash_futures_change", futures_cash-before_future),
                                 ("debt_change", debt-before_debt)):
                same(row[field], value, "Ledger flow "+field)
        cash_history.append((t, spot_cash, futures_cash, debt))
    times = {s: [t for t, _ in h] for s, h in histories.items()}
    cash_times = [r[0] for r in cash_history]
    fields = ("spot", "short", "average", "spot_cost", "realized_spot", "realized_futures",
              "funding", "fees", "liquidation_fees", "collateral")
    for row in daily:
        t = int(row["time_ns"])
        _, fs, ff, outstanding = cash_history[bisect_right(cash_times, t)-1]
        for name, value in (("free_spot", fs), ("free_futures", ff), ("debt", outstanding)):
            same(row[name], value, "Daily versus ledger "+name)
        for symbol in config.symbols:
            state = histories[symbol][bisect_right(times[symbol], t)-1][1]
            for field in fields:
                same(row[symbol+"_"+field], state[field], "Daily inventory "+symbol+"/"+field)
    for row in positions:
        t, symbol = int(row["time_ns"]), row["symbol"]
        left, right = bisect_left(times[symbol], t), bisect_right(times[symbol], t)
        candidates = histories[symbol][max(0, left-1):right]
        fields_present = [k for k in ("spot", "short", "average", "collateral") if row.get(k) is not None]
        if not any(all(abs(number(row[k])-state[k]) <= config.accounting_tolerance
                       for k in fields_present) for _, state in candidates):
            raise ValueError("Position snapshot differs from ledger pre/post states")
    return dict(passed=True, ledger_rows=len(rows), daily_links=len(daily), position_links=len(positions),
                final_free_spot=spot_cash, final_free_futures=futures_cash, final_debt=debt,
                final_inventory={s: asdict(a) for s, a in accounts.items()},
                scope="cash waterfall, debt, base inventory, fees, collateral and daily/state links; original opening-loss buffer retained")

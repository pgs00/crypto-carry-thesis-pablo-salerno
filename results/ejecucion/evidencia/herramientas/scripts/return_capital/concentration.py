"""Fixed descriptive top-k attribution with explicit sign denominators."""

from decimal import Decimal as D

from .common import number


def concentration(rows, ranks):
    pairs = [(r["identity"], number(r["net_pnl_usdt"])) for r in rows]
    if len({r[0] for r in pairs}) != len(pairs):
        raise ValueError("Duplicate concentration identity")
    gain = sum((max(p, D(0)) for _, p in pairs), D(0))
    loss = sum((max(-p, D(0)) for _, p in pairs), D(0))
    net = gain - loss
    result = []
    for sign in ("positive", "negative"):
        selected = (
            sorted(
                ((i, p) for i, p in pairs if p > 0 if sign == "positive"),
                key=lambda x: (-x[1], x[0]),
            )
            if sign == "positive"
            else sorted(((i, p) for i, p in pairs if p < 0), key=lambda x: (x[1], x[0]))
        )
        denominator = gain if sign == "positive" else loss
        for k in ranks:
            total = sum((p for _, p in selected[:k]), D(0))
            result.append(
                dict(
                    sign=sign,
                    requested_k=k,
                    effective_k=min(k, len(selected)),
                    population=len(pairs),
                    sign_population=len(selected),
                    identities=[i for i, _ in selected[:k]],
                    selected_pnl_usdt=total,
                    G_usdt=gain,
                    L_usdt=loss,
                    net_usdt=net,
                    share_sign=abs(total) / denominator if denominator else None,
                    share_net=total / net if net else None,
                    net_warning="nonpositive"
                    if net <= 0
                    else "small_relative_to_G_plus_L"
                    if net < (gain + loss) / 10
                    else "",
                )
            )
    return result

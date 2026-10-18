"""Controles complementarios del Sharpe citados en la tesina (secciones 4.1 y 4.4).

Ejecutar desde la raíz del repositorio crypto-carry-thesis-pablo-salerno:

    uv run python robustez_sharpe.py

Lee solo evidencia publicada en el repo:
  - results/base/continuo/tablas/equity_diario.csv
  - results/benchmark_sofr/evidencia/tablas/cartera_sofr_diaria.csv
  - results/complementaria/Evidencia_complementaria_Pablo_Salerno.zip
    (cash_review/daily_adjusted_equity.csv)

Calcula, para cada cartera BASE:
  1. Autocorrelación de los retornos diarios (rezagos 1 a 5).
  2. Sharpe con tasa cero: diario anualizado con raíz de 365 (el de la tesina),
     semanal (raíz de 52) y mensual (raíz de 12).
  3. Sharpe diario ajustado por autocorrelación (Lo, 2002) con 30 y 364 rezagos.
  4. Sharpe del exceso de retorno sobre la cuenta SOFR hipotética (diario y mensual).
  5. Lo mismo para el escenario con 100% de la caja remunerada a SOFR.

Los Sharpe se imprimen con cuatro decimales para que el redondeo a dos de la
tesina se pueda comprobar sin doble redondeo.
"""

import io
import math
import zipfile
from pathlib import Path

import pandas as pd

ROOT = Path(".")
EQUITY = ROOT / "results/base/continuo/tablas/equity_diario.csv"
SOFR = ROOT / "results/benchmark_sofr/evidencia/tablas/cartera_sofr_diaria.csv"
COMPL_ZIP = ROOT / "results/complementaria/Evidencia_complementaria_Pablo_Salerno.zip"
INITIAL = 10_000.0
START = pd.Timestamp("2021-12-31")


def daily_returns(equity: pd.Series) -> pd.Series:
    r = equity.pct_change()
    r.iloc[0] = equity.iloc[0] / INITIAL - 1
    return r


def sharpe(r: pd.Series, periods: int) -> float:
    return r.mean() / r.std(ddof=1) * math.sqrt(periods)


def lo_adjusted(r: pd.Series, lags: int, q: int = 365) -> float:
    s = sum((q - k) * r.autocorr(k) for k in range(1, min(lags, q - 1) + 1))
    eta = q / math.sqrt(q + 2 * s)
    return r.mean() / r.std(ddof=1) * eta


def resample_returns(level: pd.Series, rule: str) -> pd.Series:
    level = pd.concat([pd.Series([INITIAL], index=[START]), level])
    return level.resample(rule).last().pct_change().dropna()


def report(name: str, equity: pd.Series, sofr_level: pd.Series) -> None:
    r = daily_returns(equity)
    s = daily_returns(sofr_level).reindex(r.index)
    excess = r - s
    monthly = resample_returns(equity, "ME")
    monthly_sofr = resample_returns(sofr_level, "ME").reindex(monthly.index)
    print(f"\n== {name}")
    print("  Autocorrelación rezagos 1-5:", [round(float(r.autocorr(k)), 3) for k in range(1, 6)])
    print(f"  Sharpe tasa cero, diario x raíz(365): {sharpe(r, 365):.4f}")
    print(
        f"  Sharpe tasa cero, semanal x raíz(52): {sharpe(resample_returns(equity, 'W-SUN'), 52):.4f}"
    )
    print(f"  Sharpe tasa cero, mensual x raíz(12): {sharpe(monthly, 12):.4f}")
    print(f"  Sharpe ajustado Lo (2002), 30 rezagos: {lo_adjusted(r, 30):.4f}")
    print(f"  Sharpe ajustado Lo (2002), 364 rezagos: {lo_adjusted(r, 364):.4f}")
    print(f"  Sharpe exceso sobre SOFR, diario: {sharpe(excess, 365):.4f}")
    print(f"  Sharpe exceso sobre SOFR, mensual: {sharpe(monthly - monthly_sofr, 12):.4f}")
    print(f"  Meses con retorno < SOFR: {(monthly < monthly_sofr).sum()} de {len(monthly)}")


def main() -> None:
    eq = pd.read_csv(EQUITY, parse_dates=["date"])
    sofr = pd.read_csv(SOFR, parse_dates=["date"]).set_index("date")["balance_close"].astype(float)
    for strategy, label in [("conditional", "Condicional"), ("permanent", "Incondicional")]:
        e = eq[eq.strategy == strategy].set_index("date")["equity_usdt"].astype(float)
        report(f"{label}, BASE", e, sofr)
    with zipfile.ZipFile(COMPL_ZIP) as z:
        adj = pd.read_csv(
            io.BytesIO(z.read("cash_review/daily_adjusted_equity.csv")), parse_dates=["date"]
        )
    adj = adj[adj.cash_fraction.astype(float) == 1.0]
    for strategy, label in [("conditional", "Condicional"), ("permanent", "Incondicional")]:
        e = adj[adj.strategy == strategy].set_index("date")["adjusted_equity_usdt"].astype(float)
        report(f"{label}, caja 100% remunerada", e, sofr)


if __name__ == "__main__":
    main()

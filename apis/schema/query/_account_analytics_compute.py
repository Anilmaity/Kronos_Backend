"""Pure KPI + equity-curve math for accountAnalytics. No DB / ORM / graphene —
unit-tested standalone (apis/test_account_analytics_compute.py). broker_deals
profit/commission/swap are already USD; a trade's realized $ = profit+commission+swap.
"""
from __future__ import annotations

from datetime import date, datetime


def _usd(d: dict) -> float:
    return float(d.get("profit") or 0) + float(d.get("commission") or 0) + float(d.get("swap") or 0)


def _in_window(dt: datetime, lo: date, hi: date) -> bool:
    return lo <= dt.date() <= hi


def compute_account_analytics(deals: list[dict], from_date: date, to_date: date) -> dict:
    deals = sorted(deals, key=lambda d: d["deal_time"])
    # Seed: cumulative balance from ALL deals strictly before the window (incl deposits).
    seed = sum(_usd(d) for d in deals if d["deal_time"].date() < from_date)
    # current balance = cumulative over ALL deals (incl deposits), any time.
    current_balance = round(sum(_usd(d) for d in deals), 2)

    trades = [d for d in deals
              if d.get("entry_type") == "DEAL_ENTRY_OUT" and _in_window(d["deal_time"], from_date, to_date)]
    pnls = [_usd(d) for d in trades]
    n = len(trades)
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    gross_win = sum(wins)
    gross_loss = -sum(losses)
    net = round(sum(pnls), 2)

    by_day: dict = {}
    for d, p in zip(trades, pnls):
        by_day[d["deal_time"].date()] = by_day.get(d["deal_time"].date(), 0.0) + p

    # Equity curve over the window: seed carried in, then every in-window deal
    # (incl deposits so the balance line is real), running cumulative.
    curve: list[list] = []
    running = seed
    if n or any(_in_window(d["deal_time"], from_date, to_date) for d in deals):
        curve.append([from_date.isoformat(), round(running, 2)])
        for d in deals:
            if _in_window(d["deal_time"], from_date, to_date):
                running += _usd(d)
                curve.append([d["deal_time"].isoformat(), round(running, 2)])
    peak = -float("inf")
    max_dd = 0.0
    for _t, v in curve:
        peak = max(peak, v)
        max_dd = max(max_dd, peak - v)

    kpis = {
        "net_pnl_usd": net,
        "trades": n,
        "win_rate": round(100.0 * len(wins) / n, 2) if n else 0.0,
        "profit_factor": round(gross_win / gross_loss, 4) if gross_loss > 0 else None,
        "avg_win_usd": round(gross_win / len(wins), 2) if wins else 0.0,
        "avg_loss_usd": round(gross_loss / len(losses), 2) if losses else 0.0,
        "expectancy_usd": round(net / n, 2) if n else 0.0,
        "max_drawdown_usd": round(max_dd, 2),
        "best_day_usd": round(max(by_day.values()), 2) if by_day else 0.0,
        "worst_day_usd": round(min(by_day.values()), 2) if by_day else 0.0,
        "avg_trades_per_day": round(n / len(by_day), 2) if by_day else 0.0,
        "current_balance_usd": current_balance,
    }
    # Downsample curve to <= 2000 points (keep last), matching the mbt convention.
    if len(curve) > 2000:
        stride = -(-len(curve) // 2000)
        sampled = curve[::stride]
        if sampled[-1] != curve[-1]:
            sampled.append(curve[-1])
        curve = sampled
    return {"kpis": kpis, "equity_curve": curve}

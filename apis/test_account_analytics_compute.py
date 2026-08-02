from datetime import date, datetime
from django.test import SimpleTestCase
from apis.schema.query._account_analytics_compute import compute_account_analytics


def _d(dt, profit, entry="DEAL_ENTRY_OUT", dtype="DEAL_TYPE_SELL", comm=0.0, swap=0.0):
    return {"deal_time": dt, "deal_type": dtype, "entry_type": entry,
            "profit": profit, "commission": comm, "swap": swap}


class ComputeTests(SimpleTestCase):
    def test_kpis_and_curve(self):
        deals = [
            _d(datetime(2026, 6, 30, 12, 0), 1000.0, entry=None, dtype="DEAL_TYPE_BALANCE"),  # deposit pre-window
            _d(datetime(2026, 7, 1, 10, 0), 30.0),    # win  day1
            _d(datetime(2026, 7, 1, 14, 0), -10.0),   # loss day1  -> day1 net +20
            _d(datetime(2026, 7, 2, 11, 0), -40.0),   # loss day2
            _d(datetime(2026, 7, 3, 9, 0), 20.0, comm=-2.0),  # win 18 day3
            _d(datetime(2026, 7, 3, 9, 0), 0.0, entry="DEAL_ENTRY_IN"),  # open -> ignored
        ]
        out = compute_account_analytics(deals, date(2026, 7, 1), date(2026, 7, 31))
        k = out["kpis"]
        self.assertEqual(k["trades"], 4)                       # 4 OUT deals in window
        self.assertEqual(k["net_pnl_usd"], round(30 - 10 - 40 + 18, 2))   # -2.0
        self.assertEqual(k["win_rate"], 50.0)                  # 2 wins / 4
        self.assertEqual(k["profit_factor"], round(48 / 50, 4))  # gw 48 / gl 50
        self.assertEqual(k["avg_win_usd"], 24.0)               # (30+18)/2
        self.assertEqual(k["avg_loss_usd"], 25.0)              # (10+40)/2
        self.assertEqual(k["expectancy_usd"], round(-2.0 / 4, 2))
        self.assertEqual(k["best_day_usd"], 20.0)              # day1 net
        self.assertEqual(k["worst_day_usd"], -40.0)            # day2
        self.assertEqual(k["avg_trades_per_day"], round(4 / 3, 2))  # 3 trading days
        self.assertEqual(k["current_balance_usd"], 998.0)      # 1000 - 2
        # equity curve seeded at deposit (1000) carried into window, then steps
        curve = out["equity_curve"]
        self.assertEqual(curve[0][1], 1000.0)                  # seed = balance entering window
        self.assertEqual(curve[-1][1], 998.0)                  # 1000 + (-2) net
        # max drawdown: peak 1030 (after +30) -> trough 980 (after -10-40) = 50
        self.assertEqual(k["max_drawdown_usd"], 50.0)

    def test_empty_window(self):
        out = compute_account_analytics([], date(2026, 7, 1), date(2026, 7, 31))
        k = out["kpis"]
        self.assertEqual(k["trades"], 0)
        self.assertIsNone(k["profit_factor"])
        self.assertEqual(k["net_pnl_usd"], 0.0)
        self.assertEqual(out["equity_curve"], [])

    def test_no_losses_profit_factor_none(self):
        deals = [_d(datetime(2026, 7, 1, 10, 0), 5.0)]
        out = compute_account_analytics(deals, date(2026, 7, 1), date(2026, 7, 31))
        self.assertIsNone(out["kpis"]["profit_factor"])        # no losses -> undefined
        self.assertEqual(out["kpis"]["win_rate"], 100.0)

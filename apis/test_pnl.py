"""
Tests for the position PnL formula (apis.schema.types.pnl).

Regression: the resolvers computed PnL long-only — (ltp - avg_buy_price) * qty —
so a SHORT position (avg_buy_price == 0, avg_sell_price == entry) yielded
~ ltp * qty * 100 ≈ the entry price (e.g. $4,329 ≈ "4K") instead of the real
few-dollar PnL, and the sign was wrong. The formula must be directional.

(Adapted from the old apis/schema/types/test_pnl.py, which used a sys.path
hack and plain functions that ``manage.py test`` never collected.)
"""
from django.test import SimpleTestCase

from apis.schema.types import pnl


class PositionPnlTests(SimpleTestCase):
    def test_short_position_pnl_is_small_not_entry_price(self):
        # avg_buy_price == 0, avg_sell_price == entry (the bug case)
        v = pnl.position_pnl(realized_profit_loss=0, ltp=4329.33, quantity=0.01,
                             avg_buy_price=0, avg_sell_price=4329.26)
        self.assertEqual(v, -0.07)       # (4329.26 - 4329.33) * 0.01 * 100
        self.assertLess(abs(v), 1)       # never the ~4329 inflation

    def test_short_profits_when_price_falls(self):
        v = pnl.position_pnl(0, ltp=4320.0, quantity=0.01,
                             avg_buy_price=0, avg_sell_price=4330.0)
        self.assertEqual(v, 10.0)        # (4330 - 4320) * 0.01 * 100 -> short gains

    def test_long_position_matches_existing_formula(self):
        # avg_buy_price > 0, avg_sell_price == 0 — must be unchanged from before.
        v = pnl.position_pnl(0, ltp=4330.0, quantity=0.01,
                             avg_buy_price=4327.26, avg_sell_price=0)
        self.assertEqual(v, round((4330.0 - 4327.26) * 0.01 * 100, 2))   # 2.74

    def test_closed_position_uses_realized_only(self):
        # quantity 0 -> unrealized 0 regardless of side; realized * 100.
        short = pnl.position_pnl(-0.02, ltp=4331.32, quantity=0,
                                 avg_buy_price=0, avg_sell_price=4329.16)
        long = pnl.position_pnl(0.09, ltp=4331.28, quantity=0,
                                avg_buy_price=4340.60, avg_sell_price=0)
        self.assertEqual(short, -2.0)
        self.assertEqual(long, 9.0)

    def test_notional_uses_whichever_side_has_a_price(self):
        self.assertEqual(
            pnl.position_notional(0.01, avg_buy_price=0, avg_sell_price=4329.0),
            4329.0,
        )
        self.assertEqual(
            pnl.position_notional(0.01, avg_buy_price=4327.0, avg_sell_price=0),
            4327.0,
        )

    def test_percentage_guards_against_zero_notional(self):
        # never raise ZeroDivisionError (the old short path divided by avg_buy*qty == 0)
        self.assertEqual(
            pnl.position_pnl_pct(realized_profit_loss=0, ltp=4329.0, quantity=0,
                                 avg_buy_price=0, avg_sell_price=0),
            0.0,
        )

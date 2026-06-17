"""
Pure (Django-free) tests for the position PnL formula.

Regression: the resolvers computed PnL long-only — (ltp - avg_buy_price) * qty —
so a SHORT position (avg_buy_price == 0, avg_sell_price == entry) yielded
~ ltp * qty * 100 ≈ the entry price (e.g. $4,329 ≈ "4K") instead of the real
few-dollar PnL, and the sign was wrong. The formula must be directional.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))  # import the leaf module, not the apis package
import pnl


def test_short_position_pnl_is_small_not_entry_price():
    # avg_buy_price == 0, avg_sell_price == entry (the bug case)
    v = pnl.position_pnl(realized_profit_loss=0, ltp=4329.33, quantity=0.01,
                         avg_buy_price=0, avg_sell_price=4329.26)
    assert v == -0.07            # (4329.26 - 4329.33) * 0.01 * 100
    assert abs(v) < 1            # never the ~4329 inflation


def test_short_profits_when_price_falls():
    v = pnl.position_pnl(0, ltp=4320.0, quantity=0.01,
                         avg_buy_price=0, avg_sell_price=4330.0)
    assert v == 10.0             # (4330 - 4320) * 0.01 * 100  -> short gains


def test_long_position_matches_existing_formula():
    # avg_buy_price > 0, avg_sell_price == 0 — must be unchanged from before.
    v = pnl.position_pnl(0, ltp=4330.0, quantity=0.01,
                         avg_buy_price=4327.26, avg_sell_price=0)
    assert v == round((4330.0 - 4327.26) * 0.01 * 100, 2)   # 2.74


def test_closed_position_uses_realized_only():
    # quantity 0 -> unrealized 0 regardless of side; realized * 100.
    short = pnl.position_pnl(-0.02, ltp=4331.32, quantity=0, avg_buy_price=0, avg_sell_price=4329.16)
    long = pnl.position_pnl(0.09, ltp=4331.28, quantity=0, avg_buy_price=4340.60, avg_sell_price=0)
    assert short == -2.0
    assert long == 9.0


def test_notional_uses_whichever_side_has_a_price():
    assert pnl.position_notional(0.01, avg_buy_price=0, avg_sell_price=4329.0) == 4329.0
    assert pnl.position_notional(0.01, avg_buy_price=4327.0, avg_sell_price=0) == 4327.0


def test_percentage_guards_against_zero_notional():
    # never raise ZeroDivisionError (the old short path divided by avg_buy*qty == 0)
    assert pnl.position_pnl_pct(realized_profit_loss=0, ltp=4329.0, quantity=0,
                                avg_buy_price=0, avg_sell_price=0) == 0.0


if __name__ == "__main__":
    # Run standalone (no Django/graphene/pytest needed): the apis package imports
    # graphene at collection time, so this leaf test is run directly.
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn(); print(f"PASS {fn.__name__}")
        except Exception as e:
            failed += 1; print(f"FAIL {fn.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    raise SystemExit(1 if failed else 0)

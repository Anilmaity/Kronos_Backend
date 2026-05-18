"""
Tests for resolvers and models that were touched on 2026-05-18:
  - BacktestReport model + FK + GraphQL exposure
  - UserStrategyType resolvers:
      * resolve_positions     -> today's positions UNION all currently-open
      * resolve_active_positions_count -> only qty != 0, ignores date
      * resolve_total_profit_loss      -> includes XAU contract size (*100)
                                          matches PositionType.resolve_profit_loss
  - PositionType.resolve_profit_loss   -> contract-size scaling reference

Run from Kronos_Backend root:
    python manage.py test apis
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apis.models import (
    BacktestReport,
    CurrencyPair,
    Position,
    Strategy,
    StrategySignal,
    User,
    UserBroker,
    UserStrategy,
)
from apis.schema.types.position_type import PositionType
from apis.schema.types.user_strategy_type import UserStrategyType, _positions_qs


# ───────────────────────────────────────────────────────────────────────────────
# Test fixtures
# ───────────────────────────────────────────────────────────────────────────────

def _mk_user_strategy(symbol="XAU_USD", ltp="4540.00"):
    """Build a full ownership chain: User -> UserBroker -> Strategy + UserStrategy.
    Returns the UserStrategy instance.
    """
    user = User.objects.create(
        email=f"t-{uuid.uuid4()}@test.local",
        first_name="T",
        last_name="T",
    )
    cp = CurrencyPair.objects.create(symbol=symbol, name=symbol, ltp=ltp)
    ub = UserBroker.objects.create(user=user, api_key=str(uuid.uuid4()))
    strat = Strategy.objects.create(
        name=f"Test {symbol} {uuid.uuid4()}",
        currencypair=cp,
        entry_quantity=Decimal("0.01"),
        is_active=True,
    )
    us = UserStrategy.objects.create(
        strategy=strat,
        user_broker=ub,
        is_active=True,
        deployed=True,
        multiplyer=1,
    )
    return us


def _mk_position(us, *, qty, avg, ltp_override=None, realized="0.00", created_at=None):
    """Create a Position attached to the given UserStrategy.

    If ltp_override is given, the CurrencyPair.ltp is updated to it (since
    PnL formulas read from currencypair.ltp, not Position.ltp).
    """
    cp = us.strategy.currencypair
    if ltp_override is not None:
        cp.ltp = str(ltp_override)
        cp.save()
    p = Position.objects.create(
        user_strategy=us,
        currencypair=cp,
        symbol=cp.symbol,
        quantity=Decimal(str(qty)),
        avg_buy_price=Decimal(str(avg)),
        ltp=Decimal(str(ltp_override or cp.ltp)),
        realized_profit_loss=Decimal(str(realized)),
    )
    if created_at is not None:
        # Position.created_at is auto_now_add — bypass via update()
        Position.objects.filter(pk=p.pk).update(created_at=created_at)
        p.refresh_from_db()
    return p


# ───────────────────────────────────────────────────────────────────────────────
# BacktestReport model
# ───────────────────────────────────────────────────────────────────────────────

class BacktestReportModelTests(TestCase):
    def test_create_and_query(self):
        us = _mk_user_strategy()
        r = BacktestReport.objects.create(
            strategy=us.strategy,
            run_label="test_run_2026_05_18",
            trades=100,
            wins=55,
            losses=45,
            win_rate_pct=Decimal("55.00"),
            pnl_pts=Decimal("123.45"),
            max_dd_pts=Decimal("30.00"),
            profit_factor=Decimal("1.50"),
            expectancy_pts=Decimal("1.234500"),
            source_csv="test.csv",
            params_snapshot={"k": "v"},
            notes="t",
        )
        fetched = BacktestReport.objects.get(pk=r.pk)
        self.assertEqual(fetched.strategy_id, us.strategy.id)
        self.assertEqual(fetched.trades, 100)
        self.assertEqual(fetched.params_snapshot, {"k": "v"})
        self.assertEqual(fetched.strategy.backtest_reports.count(), 1)

    def test_cascade_delete_with_strategy(self):
        us = _mk_user_strategy()
        BacktestReport.objects.create(strategy=us.strategy, run_label="r")
        self.assertEqual(BacktestReport.objects.count(), 1)
        us.strategy.delete()
        self.assertEqual(BacktestReport.objects.count(), 0)


# ───────────────────────────────────────────────────────────────────────────────
# UserStrategyType resolvers — the resolver-behavior fixes from 2026-05-18
# ───────────────────────────────────────────────────────────────────────────────

class PositionFilterTests(TestCase):
    """Verifies _positions_qs returns today's positions UNION all currently-open."""

    def test_open_position_always_shown_regardless_of_date(self):
        us = _mk_user_strategy()
        five_days_ago = timezone.now() - timedelta(days=5)
        open_old = _mk_position(us, qty="0.01", avg="4500", ltp_override="4505",
                                 created_at=five_days_ago)

        # Selected date is today → no rows created today, but open_old must surface.
        qs = _positions_qs(us, date=date.today(), userstrategy_ids=[])
        ids = list(qs.values_list("id", flat=True))
        self.assertIn(open_old.id, ids)

    def test_closed_position_only_on_matching_date(self):
        us = _mk_user_strategy()
        two_days_ago = timezone.now() - timedelta(days=2)
        closed_old = _mk_position(us, qty="0", avg="4500", realized="2.50",
                                   created_at=two_days_ago)

        # Today → closed_old must NOT surface.
        qs_today = _positions_qs(us, date=date.today(), userstrategy_ids=[])
        self.assertNotIn(closed_old.id, list(qs_today.values_list("id", flat=True)))

        # On its own date → it does surface.
        qs_then = _positions_qs(us, date=two_days_ago.date(), userstrategy_ids=[])
        self.assertIn(closed_old.id, list(qs_then.values_list("id", flat=True)))

    def test_active_positions_count_ignores_date(self):
        us = _mk_user_strategy()
        five_days_ago = timezone.now() - timedelta(days=5)
        _mk_position(us, qty="0.01", avg="4500", ltp_override="4505",
                     created_at=five_days_ago)
        _mk_position(us, qty="0", avg="4500", realized="2.50",
                     created_at=five_days_ago)  # closed, should not count

        # Today, no userstrategy_ids — should still see the 1 open.
        n = UserStrategyType.resolve_active_positions_count(
            us, info=None, date="", userstrategy_ids=[]
        )
        self.assertEqual(n, 1)


class ContractSizeScalingTests(TestCase):
    """The bug fixed on 2026-05-18: strategy-total P&L was 100x smaller than
    the per-position number because the *100 XAU contract size was missing."""

    def test_per_position_and_strategy_total_agree(self):
        us = _mk_user_strategy()
        # BUY 0.01 lot @ 4500, current ltp 4502  → unrealized = (4502-4500)*0.01*100 = $2.00
        _mk_position(us, qty="0.01", avg="4500", ltp_override="4502")

        pos = us.position_set.first()
        per_position = PositionType.resolve_profit_loss(pos, info=None)
        strategy_total = UserStrategyType.resolve_total_profit_loss(
            us, info=None, date="", userstrategy_ids=[]
        )

        self.assertAlmostEqual(per_position, 2.00, places=2)
        self.assertAlmostEqual(strategy_total, 2.00, places=2)
        self.assertAlmostEqual(strategy_total, per_position, places=2)

    def test_strategy_total_includes_realized_and_unrealized(self):
        us = _mk_user_strategy()
        five_days_ago = timezone.now() - timedelta(days=5)
        # closed 5 days ago. realized_profit_loss is DECIMAL(25, 2) so it
        # only stores 2dp; the resolver multiplies it by *100 (same XAU
        # contract size as the unrealized term), so a stored 0.05 yields
        # $5.00 in the total.
        _mk_position(us, qty="0", avg="4500", realized="0.05",
                     created_at=five_days_ago)
        # open today, +$3.00 unrealized at ltp=4503 → (4503-4500)*0.01*100
        _mk_position(us, qty="0.01", avg="4500", ltp_override="4503")

        # On today's date: closed-old is NOT included (different date, qty=0).
        # Only the open one surfaces. Total = $3.00.
        total_today = UserStrategyType.resolve_total_profit_loss(
            us, info=None, date="", userstrategy_ids=[]
        )
        self.assertAlmostEqual(total_today, 3.00, places=2)

        # On the closed-position's own date: both surface → 5.00 + 3.00.
        total_then = UserStrategyType.resolve_total_profit_loss(
            us, info=None, date=five_days_ago.date(), userstrategy_ids=[]
        )
        self.assertAlmostEqual(total_then, 5.00 + 3.00, places=2)

    def test_zero_when_no_positions(self):
        us = _mk_user_strategy()
        self.assertEqual(
            UserStrategyType.resolve_total_profit_loss(
                us, info=None, date="", userstrategy_ids=[]
            ),
            0,
        )
        self.assertEqual(
            UserStrategyType.resolve_active_positions_count(
                us, info=None, date="", userstrategy_ids=[]
            ),
            0,
        )


class StrategySignalModelTests(TestCase):
    def test_create_fired_and_transition_to_placed(self):
        us = _mk_user_strategy()
        sig = StrategySignal.objects.create(
            strategy=us.strategy,
            symbol="XAU_USD",
            side="BUY",
            entry_price=Decimal("4500.00"),
            stop_loss=Decimal("4497.00"),
            take_profit=Decimal("4503.00"),
            reason="UNIT_TEST",
        )
        self.assertEqual(sig.status, "FIRED")  # default

        # Simulate a successful place_entry hooking up the position.
        pos = _mk_position(us, qty="0.01", avg="4500", ltp_override="4500")
        sig.status = "PLACED"
        sig.position = pos
        sig.save()

        sig.refresh_from_db()
        self.assertEqual(sig.status, "PLACED")
        self.assertEqual(sig.position_id, pos.id)

    def test_rejected_keeps_reason(self):
        us = _mk_user_strategy()
        sig = StrategySignal.objects.create(
            strategy=us.strategy,
            symbol="XAU_USD",
            side="SELL",
            entry_price=Decimal("4500.00"),
            reason="UNIT_TEST",
            status="REJECTED",
            rejection_reason="open_position_cap",
        )
        fetched = StrategySignal.objects.get(pk=sig.pk)
        self.assertEqual(fetched.status, "REJECTED")
        self.assertEqual(fetched.rejection_reason, "open_position_cap")
        self.assertIsNone(fetched.position_id)

    def test_cascade_delete_with_strategy(self):
        us = _mk_user_strategy()
        StrategySignal.objects.create(
            strategy=us.strategy, symbol="XAU_USD", side="BUY",
            entry_price=Decimal("4500"),
        )
        self.assertEqual(StrategySignal.objects.count(), 1)
        us.strategy.delete()
        self.assertEqual(StrategySignal.objects.count(), 0)

    def test_position_delete_nulls_link_but_keeps_signal(self):
        us = _mk_user_strategy()
        pos = _mk_position(us, qty="0.01", avg="4500", ltp_override="4500")
        sig = StrategySignal.objects.create(
            strategy=us.strategy, symbol="XAU_USD", side="BUY",
            entry_price=Decimal("4500"), status="PLACED", position=pos,
        )
        pos.delete()
        sig.refresh_from_db()
        self.assertIsNone(sig.position_id)
        self.assertEqual(sig.status, "PLACED")  # status unchanged

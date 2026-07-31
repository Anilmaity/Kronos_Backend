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
from graphql import GraphQLError

from apis.models import (
    BacktestReport,
    CurrencyPair,
    Order,
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
    cp, _ = CurrencyPair.objects.get_or_create(symbol=symbol, defaults={"name": symbol, "ltp": ltp})
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


# ───────────────────────────────────────────────────────────────────────────────
# ExitStrategy helpers — truthful success/failure (2026-06-21)
# ───────────────────────────────────────────────────────────────────────────────

from unittest.mock import MagicMock
import requests as _requests

from apis.schema.mutation.user.exit_strategy import (
    request_position_exits,
    build_exit_message,
)


class ExitStrategyHelperTests(TestCase):
    @staticmethod
    def _pos(pid="p1"):
        m = MagicMock()
        m.id = pid
        return m

    def test_all_confirmed(self):
        ok_resp = MagicMock()
        ok_resp.raise_for_status.return_value = None
        post = MagicMock(return_value=ok_resp)
        confirmed, pending, failed = request_position_exits(
            [self._pos(), self._pos()], post=post
        )
        self.assertEqual((confirmed, pending, failed), (2, 0, 0))
        self.assertEqual(post.call_count, 2)

    def test_timeout_is_pending_not_confirmed(self):
        post = MagicMock(side_effect=_requests.exceptions.Timeout())
        confirmed, pending, failed = request_position_exits([self._pos()], post=post)
        self.assertEqual((confirmed, pending, failed), (0, 1, 0))

    def test_connection_error_is_failed(self):
        post = MagicMock(side_effect=_requests.exceptions.ConnectionError())
        confirmed, pending, failed = request_position_exits([self._pos()], post=post)
        self.assertEqual((confirmed, pending, failed), (0, 0, 1))

    def test_http_error_is_failed(self):
        bad_resp = MagicMock()
        bad_resp.raise_for_status.side_effect = _requests.exceptions.HTTPError()
        post = MagicMock(return_value=bad_resp)
        confirmed, pending, failed = request_position_exits([self._pos()], post=post)
        self.assertEqual((confirmed, pending, failed), (0, 0, 1))

    def test_message_includes_pending_and_failed(self):
        self.assertEqual(build_exit_message(1, 0, 0), "Exit requested: 1 exited")
        msg = build_exit_message(1, 2, 3)
        self.assertIn("1 exited", msg)
        self.assertIn("2 pending confirmation", msg)
        self.assertIn("3 failed", msg)


# ───────────────────────────────────────────────────────────────────────────────
# SetUserStrategyMultiplier — contract pinned for the FE fix (2026-06-21)
# ───────────────────────────────────────────────────────────────────────────────

from types import SimpleNamespace

from apis.schema.mutation.user.set_user_strategy_multiplier import (
    SetUserStrategyMultiplier,
)


class SetMultiplierTests(TestCase):
    @staticmethod
    def _info(user):
        return SimpleNamespace(context=SimpleNamespace(user=user))

    def test_sets_multiplier(self):
        us = _mk_user_strategy()
        user = us.user_broker.user
        res = SetUserStrategyMultiplier.mutate(
            None, self._info(user), user_strategy_id=str(us.id), multiplier=5
        )
        us.refresh_from_db()
        self.assertEqual(us.multiplyer, 5)
        self.assertEqual(res.Response, "Success")

    def test_rejects_below_one(self):
        us = _mk_user_strategy()
        user = us.user_broker.user
        res = SetUserStrategyMultiplier.mutate(
            None, self._info(user), user_strategy_id=str(us.id), multiplier=0
        )
        self.assertIn("Multiplier must be", res.Response)
        us.refresh_from_db()
        self.assertEqual(us.multiplyer, 1)  # unchanged


# ───────────────────────────────────────────────────────────────────────────────
# Accounts: credential crypto (2026-06-22)
# ───────────────────────────────────────────────────────────────────────────────

import os
from cryptography.fernet import Fernet


class CryptoTests(TestCase):
    def setUp(self):
        os.environ["FIELD_ENCRYPTION_KEY"] = Fernet.generate_key().decode()

    def test_round_trip(self):
        from apis.crypto import encrypt_token, decrypt_token
        cipher = encrypt_token("super-secret-token-1234")
        self.assertNotEqual(cipher, "super-secret-token-1234")
        self.assertEqual(decrypt_token(cipher), "super-secret-token-1234")

    def test_empty_passthrough(self):
        from apis.crypto import encrypt_token, decrypt_token
        self.assertEqual(encrypt_token(""), "")
        self.assertEqual(decrypt_token(""), "")

    def test_missing_key_raises(self):
        os.environ.pop("FIELD_ENCRYPTION_KEY", None)
        from apis.crypto import encrypt_token
        with self.assertRaises(RuntimeError):
            encrypt_token("x")


# ───────────────────────────────────────────────────────────────────────────────
# UserBroker credential fields (2026-06-22)
# ───────────────────────────────────────────────────────────────────────────────

class UserBrokerCredentialFieldTests(TestCase):
    def test_fields_persist_to_db(self):
        us = _mk_user_strategy()
        broker = us.user_broker
        broker.label = "Primary Live"
        broker.meta_account_id = "acct-uuid-1"
        broker.meta_api_token_enc = "cipher"
        broker.meta_api_token_last4 = "1234"
        broker.save()
        # Fresh fetch (not refresh_from_db) so this actually exercises the DB
        # columns — proving the fields persist, not just that the attrs were set.
        fetched = UserBroker.objects.get(pk=broker.pk)
        self.assertEqual(fetched.label, "Primary Live")
        self.assertEqual(fetched.meta_account_id, "acct-uuid-1")
        self.assertEqual(fetched.meta_api_token_enc, "cipher")
        self.assertEqual(fetched.meta_api_token_last4, "1234")

    def test_defaults_are_empty(self):
        us = _mk_user_strategy()
        fetched = UserBroker.objects.get(pk=us.user_broker.pk)
        self.assertEqual(fetched.label, "")
        self.assertEqual(fetched.meta_account_id, "")
        self.assertEqual(fetched.meta_api_token_enc, "")
        self.assertEqual(fetched.meta_api_token_last4, "")


# ───────────────────────────────────────────────────────────────────────────────
# UserBrokerType schema — token ciphertext hidden; hasToken flag exposed (2026-06-22)
# ───────────────────────────────────────────────────────────────────────────────

from apis.schema.types.user_broker_type import UserBrokerType as _UBType


class UserBrokerTypeTests(TestCase):
    def test_has_token_reflects_presence(self):
        us = _mk_user_strategy()
        broker = us.user_broker
        broker.meta_api_token_enc = ""
        self.assertFalse(_UBType.resolve_hasToken(broker, None))
        broker.meta_api_token_enc = "cipher"
        self.assertTrue(_UBType.resolve_hasToken(broker, None))

    def test_ciphertext_field_not_in_schema(self):
        field_names = set(_UBType._meta.fields.keys())
        self.assertNotIn("metaApiTokenEnc", field_names)
        self.assertNotIn("meta_api_token_enc", field_names)
        self.assertIn("hasToken", field_names)

    def test_label_resolves_to_model_field(self):
        us = _mk_user_strategy()
        broker = us.user_broker
        broker.label = "My Live Account"
        self.assertEqual(_UBType.resolve_label(broker, None), "My Live Account")


# ───────────────────────────────────────────────────────────────────────────────
# AddAccount mutation (2026-06-22)
# ───────────────────────────────────────────────────────────────────────────────

class AddAccountTests(TestCase):
    @staticmethod
    def _info(user):
        from types import SimpleNamespace
        return SimpleNamespace(context=SimpleNamespace(user=user))

    def setUp(self):
        os.environ["FIELD_ENCRYPTION_KEY"] = Fernet.generate_key().decode()

    def test_creates_encrypted_account(self):
        from apis.schema.mutation.user.add_account import AddAccount
        from apis.crypto import decrypt_token
        us = _mk_user_strategy()
        user = us.user_broker.user
        res = AddAccount.mutate(
            None, self._info(user),
            label="Live A", meta_account_id="acct-1", meta_api_token="tok-ABCD1234",
        )
        self.assertEqual(res.Response, "Success")
        b = res.UserBroker
        self.assertEqual(b.label, "Live A")
        self.assertEqual(b.meta_account_id, "acct-1")
        self.assertEqual(b.meta_api_token_last4, "1234")
        self.assertNotEqual(b.meta_api_token_enc, "tok-ABCD1234")
        self.assertEqual(decrypt_token(b.meta_api_token_enc), "tok-ABCD1234")
        self.assertEqual(b.user_id, user.id)

    def test_missing_key_is_handled(self):
        from apis.schema.mutation.user.add_account import AddAccount
        os.environ.pop("FIELD_ENCRYPTION_KEY", None)
        us = _mk_user_strategy()
        user = us.user_broker.user
        res = AddAccount.mutate(
            None, self._info(user),
            label="X", meta_account_id="y", meta_api_token="z",
        )
        self.assertIn("encryption key", res.Response)
        self.assertIsNone(res.UserBroker)

    def test_two_accounts_get_distinct_api_keys(self):
        # Regression: the model's api_key default is a broken static string, so a
        # second AddAccount without an explicit api_key would hit the unique
        # constraint. Both creates must succeed with distinct api_keys.
        from apis.schema.mutation.user.add_account import AddAccount
        user = _mk_user_strategy().user_broker.user
        a = AddAccount.mutate(
            None, self._info(user),
            label="A", meta_account_id="a1", meta_api_token="tok-AAAA1111",
        )
        b = AddAccount.mutate(
            None, self._info(user),
            label="B", meta_account_id="b1", meta_api_token="tok-BBBB2222",
        )
        self.assertEqual(a.Response, "Success")
        self.assertEqual(b.Response, "Success")
        self.assertNotEqual(a.UserBroker.api_key, b.UserBroker.api_key)


# ───────────────────────────────────────────────────────────────────────────────
# UpdateAccount mutation (2026-06-22)
# ───────────────────────────────────────────────────────────────────────────────

class UpdateAccountTests(TestCase):
    @staticmethod
    def _info(user):
        from types import SimpleNamespace
        return SimpleNamespace(context=SimpleNamespace(user=user))

    def setUp(self):
        os.environ["FIELD_ENCRYPTION_KEY"] = Fernet.generate_key().decode()

    def _make(self, user):
        from apis.schema.mutation.user.add_account import AddAccount
        return AddAccount.mutate(
            None, self._info(user),
            label="Orig", meta_account_id="acct-1", meta_api_token="tok-OLD9999",
        ).UserBroker

    def test_label_only_keeps_token(self):
        from apis.schema.mutation.user.update_account import UpdateAccount
        us = _mk_user_strategy()
        user = us.user_broker.user
        b = self._make(user)
        old_enc = b.meta_api_token_enc
        res = UpdateAccount.mutate(None, self._info(user), id=str(b.id), label="Renamed")
        self.assertEqual(res.Response, "Success")
        b.refresh_from_db()
        self.assertEqual(b.label, "Renamed")
        self.assertEqual(b.meta_api_token_enc, old_enc)
        self.assertEqual(b.meta_api_token_last4, "9999")

    def test_new_token_reencrypts(self):
        from apis.schema.mutation.user.update_account import UpdateAccount
        from apis.crypto import decrypt_token
        us = _mk_user_strategy()
        user = us.user_broker.user
        b = self._make(user)
        res = UpdateAccount.mutate(
            None, self._info(user), id=str(b.id), meta_api_token="tok-NEW1111"
        )
        self.assertEqual(res.Response, "Success")
        b.refresh_from_db()
        self.assertEqual(b.meta_api_token_last4, "1111")
        self.assertEqual(decrypt_token(b.meta_api_token_enc), "tok-NEW1111")

    def test_other_users_account_not_found(self):
        from apis.schema.mutation.user.update_account import UpdateAccount
        owner = _mk_user_strategy().user_broker.user
        b = self._make(owner)
        other = _mk_user_strategy().user_broker.user
        res = UpdateAccount.mutate(None, self._info(other), id=str(b.id), label="hax")
        self.assertIn("does not exist", res.Response)
        self.assertIsNone(res.UserBroker)


# ───────────────────────────────────────────────────────────────────────────────
# AddStrategy deploy mutation (2026-06-22, Sub-project B)
# ───────────────────────────────────────────────────────────────────────────────

class AddStrategyDeployTests(TestCase):
    @staticmethod
    def _info(user):
        from types import SimpleNamespace
        return SimpleNamespace(context=SimpleNamespace(user=user))

    def _fresh_strategy(self):
        cp, _ = CurrencyPair.objects.get_or_create(
            symbol="XAU_USD", defaults={"name": "XAU_USD", "ltp": "4540.00"}
        )
        return Strategy.objects.create(
            name=f"Mkt {uuid.uuid4()}", currencypair=cp, is_active=True
        )

    def test_deploy_creates_live_userstrategy(self):
        from apis.schema.mutation.user.add_strategy import AddStrategy
        us = _mk_user_strategy()
        user = us.user_broker.user
        broker = us.user_broker
        strat = self._fresh_strategy()
        res = AddStrategy.mutate(
            None, self._info(user),
            strategy_id=str(strat.id), user_broker_id=str(broker.id), quantity=3,
        )
        self.assertEqual(res.Response, "Success")
        link = UserStrategy.objects.get(user_broker=broker, strategy=strat)
        self.assertTrue(link.deployed)
        self.assertTrue(link.is_active)
        self.assertEqual(link.multiplyer, 3)

    def test_duplicate_returns_already_exists(self):
        from apis.schema.mutation.user.add_strategy import AddStrategy
        us = _mk_user_strategy()
        user = us.user_broker.user
        broker = us.user_broker
        strat = self._fresh_strategy()
        AddStrategy.mutate(
            None, self._info(user),
            strategy_id=str(strat.id), user_broker_id=str(broker.id),
        )
        res = AddStrategy.mutate(
            None, self._info(user),
            strategy_id=str(strat.id), user_broker_id=str(broker.id),
        )
        self.assertIn("Already Exists", res.Response)
        self.assertEqual(
            UserStrategy.objects.filter(user_broker=broker, strategy=strat).count(), 1
        )

    def test_non_owner_account_rejected(self):
        from apis.schema.mutation.user.add_strategy import AddStrategy
        owner_us = _mk_user_strategy()
        broker = owner_us.user_broker
        other = _mk_user_strategy().user_broker.user
        strat = self._fresh_strategy()
        res = AddStrategy.mutate(
            None, self._info(other),
            strategy_id=str(strat.id), user_broker_id=str(broker.id),
        )
        self.assertIn("does not exist", res.Response)
        self.assertFalse(
            UserStrategy.objects.filter(user_broker=broker, strategy=strat).exists()
        )

    def test_missing_strategy(self):
        from apis.schema.mutation.user.add_strategy import AddStrategy
        us = _mk_user_strategy()
        user = us.user_broker.user
        res = AddStrategy.mutate(
            None, self._info(user),
            strategy_id=str(uuid.uuid4()), user_broker_id=str(us.user_broker.id),
        )
        self.assertIn("Strategy does not exist", res.Response)


class DeleteUserBrokerScopeTests(TestCase):
    @staticmethod
    def _info(user):
        from types import SimpleNamespace
        return SimpleNamespace(context=SimpleNamespace(user=user))

    def test_owner_can_delete(self):
        from apis.schema.mutation.user.delete_user_broker import DeleteUserBroker
        from apis.models import UserBroker
        us = _mk_user_strategy()
        us.delete()
        broker = us.user_broker
        user = broker.user
        res = DeleteUserBroker.mutate(None, self._info(user), broker_id=str(broker.id))
        self.assertEqual(res.Response, 'Success')
        self.assertFalse(UserBroker.objects.filter(id=broker.id).exists())

    def test_non_owner_cannot_delete(self):
        from apis.schema.mutation.user.delete_user_broker import DeleteUserBroker
        from apis.models import UserBroker
        owner_us = _mk_user_strategy()
        broker = owner_us.user_broker
        other = _mk_user_strategy().user_broker.user
        res = DeleteUserBroker.mutate(None, self._info(other), broker_id=str(broker.id))
        self.assertIn('Not Found', res.Response)
        self.assertTrue(UserBroker.objects.filter(id=broker.id).exists())


class BackfillTgSignalsCommandTests(TestCase):
    """The backfill_tg_signals management command turns historical telegram
    copy-trade positions into StrategySignal rows so they show on the Signals tab."""

    def _neymar_us(self):
        us = _mk_user_strategy()
        us.strategy.name = f"Neymar Telegram Copy {uuid.uuid4()}"
        us.strategy.save()
        return us

    def test_creates_one_signal_per_position_and_is_idempotent(self):
        from django.core.management import call_command

        us = self._neymar_us()
        _mk_position(us, qty="0.04", avg="4100.00")
        _mk_position(us, qty="0.04", avg="4200.00")
        # A non-telegram strategy's position must be ignored.
        other = _mk_user_strategy()
        _mk_position(other, qty="0.04", avg="3000.00")

        self.assertEqual(StrategySignal.objects.filter(strategy=us.strategy).count(), 0)
        call_command("backfill_tg_signals", "--commit")

        sigs = StrategySignal.objects.filter(strategy=us.strategy)
        self.assertEqual(sigs.count(), 2)
        self.assertTrue(all(s.status == "PLACED" for s in sigs))
        self.assertTrue(all(s.position_id is not None for s in sigs))
        # Unrelated strategy untouched.
        self.assertEqual(StrategySignal.objects.filter(strategy=other.strategy).count(), 0)

        # Re-running creates nothing (positions already linked).
        call_command("backfill_tg_signals", "--commit")
        self.assertEqual(StrategySignal.objects.filter(strategy=us.strategy).count(), 2)

    def test_dry_run_writes_nothing(self):
        from django.core.management import call_command

        us = self._neymar_us()
        _mk_position(us, qty="0.04", avg="4100.00")
        call_command("backfill_tg_signals")  # no --commit
        self.assertEqual(StrategySignal.objects.filter(strategy=us.strategy).count(), 0)


# ───────────────────────────────────────────────────────────────────────────────
# Strategy Archive (2026-06-29)
# ───────────────────────────────────────────────────────────────────────────────
from types import SimpleNamespace as _SNS

from apis.schema.mutation.user.archive_strategy import ArchiveStrategy
from apis.schema.mutation.user.unarchive_strategy import UnarchiveStrategy
from apis.schema.query.archived_strategies import ArchivedStrategies
from apis.schema.types.user_broker_type import UserBrokerType


def _archive_info(user):
    return _SNS(context=_SNS(user=user))


class ArchiveModelTests(TestCase):
    def test_default_archived_false(self):
        us = _mk_user_strategy()
        self.assertFalse(us.archived)


class ArchiveMutationTests(TestCase):
    def test_archive_sets_flags_and_stops_strategy(self):
        us = _mk_user_strategy()
        user = us.user_broker.user
        res = ArchiveStrategy.mutate(None, _archive_info(user), user_strategy_id=str(us.id))
        us.refresh_from_db()
        self.assertEqual(res.Response, "Success")
        self.assertTrue(us.archived)
        self.assertFalse(us.deployed)
        self.assertFalse(us.is_active)

    def test_archive_blocked_when_open_position(self):
        us = _mk_user_strategy()
        _mk_position(us, qty="0.01", avg="4000")  # open position (qty != 0)
        user = us.user_broker.user
        res = ArchiveStrategy.mutate(None, _archive_info(user), user_strategy_id=str(us.id))
        us.refresh_from_db()
        self.assertIn("open positions", res.Response.lower())
        self.assertFalse(us.archived)  # unchanged

    def test_archive_rejected_for_non_owner(self):
        us = _mk_user_strategy()
        other = User.objects.create(email=f"x-{uuid.uuid4()}@test.local")
        res = ArchiveStrategy.mutate(None, _archive_info(other), user_strategy_id=str(us.id))
        us.refresh_from_db()
        self.assertEqual(res.Response, "Strategy Does Not Exist")
        self.assertFalse(us.archived)

    def test_unarchive_clears_flag(self):
        us = _mk_user_strategy()
        us.archived = True
        us.save()
        user = us.user_broker.user
        res = UnarchiveStrategy.mutate(None, _archive_info(user), user_strategy_id=str(us.id))
        us.refresh_from_db()
        self.assertEqual(res.Response, "Success")
        self.assertFalse(us.archived)


class ArchiveQueryTests(TestCase):
    def test_archived_query_returns_only_archived_owned(self):
        us = _mk_user_strategy()
        user = us.user_broker.user
        us.archived = True
        us.save()
        result = list(ArchivedStrategies.resolve_archived_strategies(None, _archive_info(user)))
        self.assertEqual([s.id for s in result], [us.id])

    def test_broker_resolver_excludes_archived(self):
        us = _mk_user_strategy()
        ub = us.user_broker
        # not archived -> visible
        visible = list(UserBrokerType.resolve_userstrategys(ub, None))
        self.assertIn(us.id, [s.id for s in visible])
        # archived -> hidden
        us.archived = True
        us.save()
        hidden = list(UserBrokerType.resolve_userstrategys(ub, None))
        self.assertNotIn(us.id, [s.id for s in hidden])


# ───────────────────────────────────────────────────────────────────────────────
# Strategy Manager (2026-07-02)
# ───────────────────────────────────────────────────────────────────────────────

from apis.models import (
    ManagedStrategy,
    ManagerAction,
    ManagerConfig,
    RegimeSnapshot,
)
from apis.schema.mutation.user.arm_strategy import ArmStrategy
from apis.schema.mutation.user.set_manager_mode import SetManagerMode
from apis.schema.mutation.user.update_manager_config import UpdateManagerConfig
from apis.schema.query.strategy_manager_state import StrategyManagerState
from apis.schema.query.regime_history import RegimeHistory


def _mk_managed(us=None, **kwargs):
    if us is None:
        us = _mk_user_strategy()
    defaults = dict(user_strategy=us, slot="trend", policy_key="always_on")
    defaults.update(kwargs)
    return ManagedStrategy.objects.create(**defaults)


class ManagerModelDefaultTests(TestCase):
    def test_regime_snapshot_defaults(self):
        snap = RegimeSnapshot.objects.create()
        self.assertEqual(snap.symbol, "XAU_USD")
        self.assertEqual(snap.d1_bias, "neutral")
        self.assertEqual(snap.h4_bias, "neutral")
        self.assertEqual(snap.vol_regime, "NORMAL")
        self.assertEqual(snap.trend_regime, "MIXED")
        self.assertEqual(snap.session, "ASIA")
        self.assertFalse(snap.market_closed)
        self.assertEqual(snap.details, {})

    def test_managed_strategy_defaults_are_safe(self):
        ms = _mk_managed()
        self.assertEqual(ms.arm_mode, "OFF")
        self.assertFalse(ms.live_eligible)
        self.assertFalse(ms.desired_active)
        self.assertEqual(ms.last_reason, "")
        self.assertIsNone(ms.last_evaluated_at)
        self.assertEqual(ms.policy_params, {})

    def test_managed_strategy_unique_per_user_strategy(self):
        ms = _mk_managed()
        from django.db import IntegrityError, transaction
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ManagedStrategy.objects.create(user_strategy=ms.user_strategy)

    def test_manager_config_defaults(self):
        cfg = ManagerConfig.objects.create()
        self.assertEqual(cfg.master_mode, "OFF")
        self.assertEqual(cfg.kill_switch_loss_usd, Decimal("150.00"))
        self.assertEqual(cfg.max_concurrent_positions, 3)
        self.assertEqual(cfg.state, {})

    def test_manager_action_nullable_fk_survives_ms_delete(self):
        ms = _mk_managed()
        act = ManagerAction.objects.create(
            managed_strategy=ms, action="PAUSE", reason="test", regime={"s": "ASIA"}
        )
        ms.delete()
        act.refresh_from_db()
        self.assertIsNone(act.managed_strategy_id)
        self.assertEqual(act.action, "PAUSE")


class StrategyManagerStateQueryTests(TestCase):
    def test_manager_config_created_default_off_when_absent(self):
        us = _mk_user_strategy()
        user = us.user_broker.user
        self.assertEqual(ManagerConfig.objects.count(), 0)
        cfg = StrategyManagerState.resolve_manager_config(None, _archive_info(user))
        self.assertEqual(ManagerConfig.objects.count(), 1)
        self.assertEqual(cfg.master_mode, "OFF")
        # Second call reuses the singleton.
        cfg2 = StrategyManagerState.resolve_manager_config(None, _archive_info(user))
        self.assertEqual(ManagerConfig.objects.count(), 1)
        self.assertEqual(cfg2.id, cfg.id)

    def test_managed_strategies_scoped_to_owner(self):
        mine = _mk_managed()
        other = _mk_managed()  # different user chain
        user = mine.user_strategy.user_broker.user
        result = list(
            StrategyManagerState.resolve_managed_strategies(None, _archive_info(user))
        )
        ids = [m.id for m in result]
        self.assertIn(mine.id, ids)
        self.assertNotIn(other.id, ids)

    def test_latest_regime_returns_newest_for_symbol(self):
        us = _mk_user_strategy()
        user = us.user_broker.user
        RegimeSnapshot.objects.create(symbol="XAU_USD", vol_regime="LOW")
        newest = RegimeSnapshot.objects.create(symbol="XAU_USD", vol_regime="HIGH")
        RegimeSnapshot.objects.create(symbol="BTC_USD", vol_regime="EXTREME")
        got = StrategyManagerState.resolve_latest_regime(
            None, _archive_info(user), symbol="XAU_USD"
        )
        self.assertEqual(got.id, newest.id)
        self.assertEqual(got.vol_regime, "HIGH")

    def test_manager_actions_limited_and_newest_first(self):
        us = _mk_user_strategy()
        user = us.user_broker.user
        now = timezone.now()
        for i in range(5):
            a = ManagerAction.objects.create(action="INFO", reason=f"r{i}")
            # auto_now_add stamps collide inside a tight loop → make ordering
            # deterministic by spacing created_at explicitly.
            ManagerAction.objects.filter(pk=a.pk).update(
                created_at=now - timedelta(seconds=5 - i)
            )
        got = list(
            StrategyManagerState.resolve_manager_actions(
                None, _archive_info(user), limit=3
            )
        )
        self.assertEqual(len(got), 3)
        self.assertEqual(got[0].reason, "r4")

    def test_regime_history_window(self):
        us = _mk_user_strategy()
        user = us.user_broker.user
        old = RegimeSnapshot.objects.create(symbol="XAU_USD")
        RegimeSnapshot.objects.filter(pk=old.pk).update(
            created_at=timezone.now() - timedelta(hours=48)
        )
        recent = RegimeSnapshot.objects.create(symbol="XAU_USD")
        got = list(
            RegimeHistory.resolve_regime_history(
                None, _archive_info(user), symbol="XAU_USD", hours=24
            )
        )
        ids = [s.id for s in got]
        self.assertIn(recent.id, ids)
        self.assertNotIn(old.id, ids)


class ArmStrategyMutationTests(TestCase):
    def test_live_rejected_when_not_eligible(self):
        ms = _mk_managed(live_eligible=False)
        user = ms.user_strategy.user_broker.user
        res = ArmStrategy.mutate(
            None, _archive_info(user),
            managed_strategy_id=str(ms.id), arm_mode="LIVE",
        )
        ms.refresh_from_db()
        self.assertIn("live-eligible", res.Response)
        self.assertEqual(ms.arm_mode, "OFF")  # unchanged

    def test_live_accepted_when_eligible(self):
        ms = _mk_managed(live_eligible=True)
        user = ms.user_strategy.user_broker.user
        res = ArmStrategy.mutate(
            None, _archive_info(user),
            managed_strategy_id=str(ms.id), arm_mode="LIVE",
        )
        ms.refresh_from_db()
        self.assertEqual(res.Response, "Success")
        self.assertEqual(ms.arm_mode, "LIVE")

    def test_paper_allowed_without_eligibility(self):
        ms = _mk_managed(live_eligible=False)
        user = ms.user_strategy.user_broker.user
        res = ArmStrategy.mutate(
            None, _archive_info(user),
            managed_strategy_id=str(ms.id), arm_mode="PAPER",
        )
        ms.refresh_from_db()
        self.assertEqual(res.Response, "Success")
        self.assertEqual(ms.arm_mode, "PAPER")

    def test_invalid_mode_rejected(self):
        ms = _mk_managed()
        user = ms.user_strategy.user_broker.user
        res = ArmStrategy.mutate(
            None, _archive_info(user),
            managed_strategy_id=str(ms.id), arm_mode="YOLO",
        )
        ms.refresh_from_db()
        self.assertIn("Invalid arm mode", res.Response)
        self.assertEqual(ms.arm_mode, "OFF")

    def test_non_owner_rejected(self):
        ms = _mk_managed(live_eligible=True)
        other = _mk_user_strategy().user_broker.user
        res = ArmStrategy.mutate(
            None, _archive_info(other),
            managed_strategy_id=str(ms.id), arm_mode="PAPER",
        )
        ms.refresh_from_db()
        self.assertEqual(res.Response, "Managed Strategy Does Not Exist")
        self.assertEqual(ms.arm_mode, "OFF")


class SetManagerModeMutationTests(TestCase):
    def test_flips_on_then_off(self):
        us = _mk_user_strategy()
        user = us.user_broker.user
        res = SetManagerMode.mutate(None, _archive_info(user), master_mode="ON")
        self.assertEqual(res.Response, "Success")
        self.assertEqual(res.ManagerConfig.master_mode, "ON")
        self.assertEqual(ManagerConfig.objects.count(), 1)

        res = SetManagerMode.mutate(None, _archive_info(user), master_mode="OFF")
        self.assertEqual(res.Response, "Success")
        self.assertEqual(
            ManagerConfig.objects.order_by("created_at").first().master_mode, "OFF"
        )
        self.assertEqual(ManagerConfig.objects.count(), 1)  # still singleton

    def test_invalid_mode_rejected(self):
        us = _mk_user_strategy()
        user = us.user_broker.user
        res = SetManagerMode.mutate(None, _archive_info(user), master_mode="MAYBE")
        self.assertIn("Invalid mode", res.Response)
        self.assertEqual(ManagerConfig.objects.count(), 0)  # nothing created


class UpdateManagerConfigMutationTests(TestCase):
    def test_updates_both_guards(self):
        us = _mk_user_strategy()
        user = us.user_broker.user
        res = UpdateManagerConfig.mutate(
            None, _archive_info(user),
            kill_switch_loss_usd=200.0, max_concurrent_positions=5,
        )
        self.assertEqual(res.Response, "Success")
        cfg = ManagerConfig.objects.get()
        self.assertEqual(cfg.kill_switch_loss_usd, Decimal("200.00"))
        self.assertEqual(cfg.max_concurrent_positions, 5)
        self.assertEqual(cfg.master_mode, "OFF")  # untouched

    def test_rejects_nonpositive_kill_switch(self):
        us = _mk_user_strategy()
        user = us.user_broker.user
        res = UpdateManagerConfig.mutate(
            None, _archive_info(user), kill_switch_loss_usd=-10.0,
        )
        self.assertIn("positive", res.Response)

    def test_rejects_zero_max_positions(self):
        us = _mk_user_strategy()
        user = us.user_broker.user
        res = UpdateManagerConfig.mutate(
            None, _archive_info(user), max_concurrent_positions=0,
        )
        self.assertIn("at least 1", res.Response)


class ManagedStrategyTypeResolverTests(TestCase):
    def test_strategy_name_and_open_positions(self):
        from apis.schema.types.managed_strategy_type import ManagedStrategyType
        ms = _mk_managed()
        us = ms.user_strategy
        _mk_position(us, qty="0.01", avg="4500")            # open
        _mk_position(us, qty="0", avg="4500", realized="1") # closed
        self.assertEqual(
            ManagedStrategyType.resolve_strategyName(ms, None), us.strategy.name
        )
        self.assertEqual(ManagedStrategyType.resolve_openPositions(ms, None), 1)

    def test_today_pnl_sums_only_today(self):
        from apis.schema.types.managed_strategy_type import ManagedStrategyType
        ms = _mk_managed()
        us = ms.user_strategy
        _mk_position(us, qty="0", avg="4500", realized="2.50")  # today
        _mk_position(
            us, qty="0", avg="4500", realized="9.99",
            created_at=timezone.now() - timedelta(days=3),
        )  # not today
        self.assertAlmostEqual(
            ManagedStrategyType.resolve_todayPnl(ms, None), 2.50, places=2
        )


# ───────────────────────────────────────────────────────────────────────────────
# UserStrategyType.resolve_brokerName (2026-07-02 /manager regression)
# ───────────────────────────────────────────────────────────────────────────────

class BrokerNameResolverTests(TestCase):
    """UserBroker lost its `broker` FK in the MetaAPI migration, but the
    resolver still dereferenced user_broker.broker.name — any query selecting
    brokerName (manager tab, archive tab) errored the whole GraphQL response."""

    def test_returns_label_when_set(self):
        us = _mk_user_strategy()
        us.user_broker.label = "FundingPips Anil"
        us.user_broker.save()
        self.assertEqual(
            UserStrategyType.resolve_brokerName(us, None), "FundingPips Anil"
        )

    def test_falls_back_to_meta_account_id(self):
        us = _mk_user_strategy()
        us.user_broker.meta_account_id = "5216074f-abcd"
        us.user_broker.save()
        self.assertEqual(
            UserStrategyType.resolve_brokerName(us, None), "5216074f-abcd"
        )

    def test_none_when_nothing_set(self):
        us = _mk_user_strategy()
        self.assertIsNone(UserStrategyType.resolve_brokerName(us, None))


# ---------------------------------------------------------------------------
# ManagerBacktestRun (2026-07-31 Manager Backtest tab, plan Task 1)
# ---------------------------------------------------------------------------

class ManagerBacktestRunModelTests(TestCase):
    def test_manager_backtest_run_defaults(self):
        from apis.models import ManagerBacktestRun

        run = ManagerBacktestRun.objects.create(
            label="audit_2026-01-01_2026-07-01",
            period_start=date(2026, 1, 1),
            period_end=date(2026, 7, 1),
        )
        run.refresh_from_db()
        self.assertEqual(run.status, "PENDING")
        self.assertEqual(run.progress_pct, 0.0)
        self.assertEqual(run.params, {})
        self.assertIsNone(run.result)
        self.assertEqual(run.error, "")
        self.assertIsNone(run.requested_by)


# ---------------------------------------------------------------------------
# Manager Backtest mutations + queries (plan Tasks 2-3)
# ---------------------------------------------------------------------------

from types import SimpleNamespace


def _auth_info(user):
    return SimpleNamespace(context=SimpleNamespace(user=user))


def _mk_run(**kw):
    from apis.models import ManagerBacktestRun
    defaults = dict(
        label="r", period_start=date(2026, 1, 1), period_end=date(2026, 2, 1))
    defaults.update(kw)
    return ManagerBacktestRun.objects.create(**defaults)


class RunManagerBacktestTests(TestCase):
    def setUp(self):
        from apis.models import ManagedStrategy
        self.us = _mk_user_strategy()
        self.user = self.us.user_broker.user
        self.ms = ManagedStrategy.objects.create(
            user_strategy=self.us, slot="scalp", policy_key="always_on",
            policy_params={"x": 1}, arm_mode="LIVE",
        )

    def _mutate(self, **kw):
        from apis.schema.mutation.user.run_manager_backtest import RunManagerBacktest
        args = dict(period_start=date(2026, 1, 1), period_end=date(2026, 3, 1))
        args.update(kw)
        return RunManagerBacktest.mutate(None, _auth_info(self.user), **args)

    def test_run_manager_backtest_creates_pending(self):
        from apis.models import ManagerBacktestRun
        res = self._mutate()
        self.assertTrue(res.ok, res.error)
        run = ManagerBacktestRun.objects.get(id=res.run_id)
        self.assertEqual(run.status, "PENDING")
        self.assertEqual(run.label, "audit_2026-01-01_2026-03-01")
        self.assertEqual(run.params["spread_pts"], 0.30)
        self.assertEqual(run.params["kill_switch_usd"], 150.0)
        self.assertEqual(run.params["include_ungated"], False)
        snap = run.params["roster_snapshot"]
        self.assertEqual(len(snap), 1)
        self.assertEqual(snap[0]["name"], self.us.strategy.name)
        self.assertEqual(snap[0]["policy_key"], "always_on")
        self.assertEqual(snap[0]["policy_params"], {"x": 1})
        self.assertEqual(run.requested_by, self.user)

    def test_off_strategies_excluded_from_snapshot(self):
        self.ms.arm_mode = "OFF"
        self.ms.save()
        res = self._mutate()
        from apis.models import ManagerBacktestRun
        run = ManagerBacktestRun.objects.get(id=res.run_id)
        self.assertEqual(run.params["roster_snapshot"], [])

    def test_run_manager_backtest_rejects_bad_window(self):
        res = self._mutate(period_start=date(2026, 3, 1), period_end=date(2026, 3, 1))
        self.assertFalse(res.ok)
        res = self._mutate(period_end=date.today() + timedelta(days=2))
        self.assertFalse(res.ok)
        res = self._mutate(period_start=date(2025, 1, 1), period_end=date(2026, 3, 1))
        self.assertFalse(res.ok)
        self.assertIn("366", res.error)

    def test_run_manager_backtest_queue_cap(self):
        for i in range(3):
            _mk_run(label=f"q{i}", status="PENDING" if i else "RUNNING")
        res = self._mutate()
        self.assertFalse(res.ok)
        self.assertIn("queue full", res.error)

    def test_cancel_manager_backtest(self):
        from apis.schema.mutation.user.cancel_manager_backtest import (
            CancelManagerBacktest,
        )
        from apis.models import ManagerBacktestRun
        run = _mk_run(status="PENDING")
        res = CancelManagerBacktest.mutate(None, _auth_info(self.user), run_id=run.id)
        self.assertTrue(res.ok)
        run.refresh_from_db()
        self.assertEqual(run.status, "CANCELLED")
        done = _mk_run(status="DONE")
        res = CancelManagerBacktest.mutate(None, _auth_info(self.user), run_id=done.id)
        self.assertFalse(res.ok)


class ManagerBacktestQueryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(
            email=f"q-{uuid.uuid4()}@test.local", first_name="Q", last_name="Q")

    def test_runs_list_newest_first(self):
        from apis.models import ManagerBacktestRun
        from apis.schema.query.manager_backtest_runs import ManagerBacktestRuns
        a = _mk_run(label="older")
        b = _mk_run(label="newer", status="DONE")
        # auto_now_add stamps both rows in the same instant on SQLite; separate
        # them explicitly so the -created_at ordering assertion is deterministic.
        ManagerBacktestRun.objects.filter(id=a.id).update(
            created_at=timezone.now() - timedelta(minutes=5))
        rows = ManagerBacktestRuns.resolve_managerBacktestRuns(
            None, _auth_info(self.user))
        labels = [r.label for r in rows]
        self.assertEqual(labels[:2], ["newer", "older"])

    def test_run_detail_roundtrips_result_json(self):
        from apis.schema.query.manager_backtest_run import ManagerBacktestRun as Q
        payload = {"summary": {"gated": {"pnl_pts": 12.5}}, "notes": ["n1"]}
        run = _mk_run(status="DONE", result=payload)
        got = Q.resolve_managerBacktestRun(None, _auth_info(self.user), runId=run.id)
        self.assertEqual(got.result, payload)
        self.assertIsNone(
            Q.resolve_managerBacktestRun(None, _auth_info(self.user),
                                         runId=uuid.uuid4()))


# ---------------------------------------------------------------------------
# pnlCalendar query (Reports tab)
# ---------------------------------------------------------------------------

class PnlCalendarTests(TestCase):
    def setUp(self):
        from apis.schema.query.pnl_calendar import PnlCalendar
        self.PnlCalendar = PnlCalendar
        self.us = _mk_user_strategy()
        self.user = self.us.user_broker.user

    def _close(self, us, realized, exit_dt, entry_shift_h=2, with_order=True):
        """Closed position realized at exit_dt (stored wall clock). The closing
        Order carries exit_dt; created_at/modified_at are decoys."""
        pos = _mk_position(us, qty=0, avg="3300", realized=str(realized),
                           created_at=exit_dt - timedelta(hours=entry_shift_h))
        if with_order:
            o = Order.objects.create(symbol="XAU_USD", position=pos,
                                     condition="EXIT", side="SELL",
                                     user_broker=us.user_broker)
            Order.objects.filter(id=o.id).update(created_at=exit_dt)
        # reconciler-touch decoy: modified_at lands days later
        Position.objects.filter(id=pos.id).update(
            modified_at=exit_dt + timedelta(days=3))
        return pos

    def _resolve(self, **kw):
        return self.PnlCalendar.resolve_pnlCalendar(None, _auth_info(self.user), **kw)

    def _mk_second_broker(self, user, symbol="XAU_USD", ltp="4540.00"):
        """Second UserBroker + UserStrategy owned by the SAME user (multi-account
        per user) -- distinct from _mk_user_strategy(), which always creates a
        brand-new owning User. Used for same-user accounts/userBrokerId tests."""
        cp, _ = CurrencyPair.objects.get_or_create(
            symbol=symbol, defaults={"name": symbol, "ltp": ltp})
        ub = UserBroker.objects.create(user=user, api_key=str(uuid.uuid4()))
        strat = Strategy.objects.create(
            name=f"Test {symbol} {uuid.uuid4()}", currencypair=cp,
            entry_quantity=Decimal("0.01"), is_active=True)
        return UserStrategy.objects.create(
            strategy=strat, user_broker=ub, is_active=True, deployed=True,
            multiplyer=1)

    def test_day_bucketing_and_usd(self):
        self._close(self.us, "0.5", datetime(2026, 7, 10, 10, 0))
        self._close(self.us, "-0.2", datetime(2026, 7, 10, 15, 0))
        self._close(self.us, "0.1", datetime(2026, 7, 11, 9, 0))
        result = self._resolve(year=2026, month=7)
        self.assertEqual(len(result.days), 2)
        self.assertEqual(result.days[0].date, date(2026, 7, 10))
        self.assertAlmostEqual(result.days[0].pnlUsd, 30.0)
        self.assertEqual(result.days[0].trades, 2)
        self.assertEqual(result.days[1].date, date(2026, 7, 11))
        self.assertAlmostEqual(result.days[1].pnlUsd, 10.0)
        self.assertEqual(result.days[1].trades, 1)
        self.assertEqual(result.monthTrades, 3)

    def test_exit_order_beats_modified_at(self):
        # Order.created_at = 07-10 (the real exit day); modified_at is forced
        # to 07-13 by the reconciler-touch decoy inside _close(). Attribution
        # must follow the exit Order, not the leaky modified_at.
        self._close(self.us, "0.3", datetime(2026, 7, 10, 12, 0))
        result = self._resolve(year=2026, month=7)
        self.assertEqual(len(result.days), 1)
        self.assertEqual(result.days[0].date, date(2026, 7, 10))

    def test_fallback_without_exit_order(self):
        # No EXIT order -> falls back to modified_at (which _close() sets to
        # exit_dt + 3 days).
        self._close(self.us, "0.2", datetime(2026, 7, 10, 12, 0), with_order=False)
        result = self._resolve(year=2026, month=7)
        self.assertEqual(len(result.days), 1)
        self.assertEqual(result.days[0].date, date(2026, 7, 13))

    def test_month_window_excludes_neighbors(self):
        self._close(self.us, "0.4", datetime(2026, 6, 30, 12, 0))
        self._close(self.us, "0.4", datetime(2026, 8, 1, 12, 0))
        result = self._resolve(year=2026, month=7)
        self.assertEqual(result.days, [])
        self.assertEqual(result.monthTrades, 0)

    def test_all_accounts_vs_filter(self):
        # Second account for the SAME user (not a different owner -- see
        # test_other_users_data_hidden_from_days_and_accounts below for the
        # cross-user boundary, which the non-superuser scoping must enforce).
        us2 = self._mk_second_broker(self.user)
        self._close(self.us, "0.5", datetime(2026, 7, 10, 10, 0))
        self._close(us2, "0.2", datetime(2026, 7, 10, 10, 0))

        result_all = self._resolve(year=2026, month=7)
        self.assertEqual(result_all.monthTrades, 2)
        self.assertAlmostEqual(result_all.monthPnlUsd, 70.0)
        account_ids = {str(a.id) for a in result_all.accounts}
        self.assertIn(str(self.us.user_broker_id), account_ids)
        self.assertIn(str(us2.user_broker_id), account_ids)
        active_flags = {str(a.id): a.isActive for a in result_all.accounts}
        self.assertTrue(active_flags[str(self.us.user_broker_id)])

        result_filtered = self._resolve(
            year=2026, month=7, userBrokerId=self.us.user_broker_id)
        self.assertEqual(result_filtered.monthTrades, 1)
        self.assertAlmostEqual(result_filtered.monthPnlUsd, 50.0)

    def test_other_users_data_hidden_from_days_and_accounts(self):
        # A second user's own broker + closed position must be invisible to
        # self.user's (non-superuser) days AND accounts -- mirrors
        # StrategyManagerState.resolve_managed_strategies's ownership scoping.
        other_us = _mk_user_strategy()
        self._close(self.us, "0.5", datetime(2026, 7, 10, 10, 0))
        self._close(other_us, "0.4", datetime(2026, 7, 10, 10, 0))

        result = self._resolve(year=2026, month=7)
        self.assertEqual(result.monthTrades, 1)
        self.assertAlmostEqual(result.monthPnlUsd, 50.0)
        self.assertEqual(len(result.days), 1)
        self.assertEqual(result.days[0].trades, 1)
        self.assertAlmostEqual(result.days[0].pnlUsd, 50.0)

        account_ids = {str(a.id) for a in result.accounts}
        self.assertIn(str(self.us.user_broker_id), account_ids)
        self.assertNotIn(str(other_us.user_broker_id), account_ids)

    def test_superuser_sees_all_users_data(self):
        other_us = _mk_user_strategy()
        self._close(self.us, "0.5", datetime(2026, 7, 10, 10, 0))
        self._close(other_us, "0.4", datetime(2026, 7, 10, 10, 0))

        admin = User.objects.create(
            email=f"admin-{uuid.uuid4()}@test.local", first_name="A", last_name="A",
            is_superuser=True)
        result = self.PnlCalendar.resolve_pnlCalendar(
            None, _auth_info(admin), year=2026, month=7)

        self.assertEqual(result.monthTrades, 2)
        self.assertAlmostEqual(result.monthPnlUsd, 90.0)
        self.assertEqual(len(result.days), 1)
        self.assertEqual(result.days[0].trades, 2)

        account_ids = {str(a.id) for a in result.accounts}
        self.assertIn(str(self.us.user_broker_id), account_ids)
        self.assertIn(str(other_us.user_broker_id), account_ids)

    def test_open_positions_excluded(self):
        _mk_position(self.us, qty=1, avg="3300", realized="0.9",
                     created_at=datetime(2026, 7, 10, 10, 0))
        result = self._resolve(year=2026, month=7)
        self.assertEqual(result.days, [])
        self.assertEqual(result.monthTrades, 0)

    def test_win_loss_days(self):
        # 07-10 net > 0 (win); 07-11 net < 0 (loss); 07-12 net == 0.0 (neither).
        self._close(self.us, "0.5", datetime(2026, 7, 10, 10, 0))
        self._close(self.us, "-0.5", datetime(2026, 7, 11, 10, 0))
        self._close(self.us, "0.3", datetime(2026, 7, 12, 9, 0))
        self._close(self.us, "-0.3", datetime(2026, 7, 12, 11, 0))
        result = self._resolve(year=2026, month=7)
        self.assertEqual(result.winDays, 1)
        self.assertEqual(result.lossDays, 1)

    def test_validation(self):
        with self.assertRaises(GraphQLError):
            self._resolve(year=2026, month=13)
        with self.assertRaises(GraphQLError):
            self._resolve(year=2019, month=7)

    def test_symbol_without_factor_falls_back_to_default(self):
        # _USD_PER_PNL_UNIT only has a real entry for XAU_USD today. A symbol
        # absent from the map (e.g. XAG_USD) must still convert -- at the
        # _DEFAULT_USD_PER_PNL_UNIT (100.0) -- documenting today's XAU-only
        # assumption. When XAG gets its own real contract-size factor, this
        # test's expected value changes accordingly.
        xag_us = self._mk_second_broker(self.user, symbol="XAG_USD")
        self._close(xag_us, "0.5", datetime(2026, 7, 10, 10, 0))
        result = self._resolve(year=2026, month=7)
        self.assertEqual(len(result.days), 1)
        self.assertAlmostEqual(result.days[0].pnlUsd, 50.0)
        self.assertAlmostEqual(result.monthPnlUsd, 50.0)

    def test_userBrokerId_for_other_users_broker_returns_empty(self):
        # A non-superuser passing another user's userBrokerId must not see
        # that account's days/totals -- the userBrokerId filter is applied
        # on top of, not instead of, the ownership scope. The requesting
        # user's own accounts list is still returned (unaffected by the
        # foreign userBrokerId).
        other_us = _mk_user_strategy()
        self._close(self.us, "0.5", datetime(2026, 7, 10, 10, 0))
        self._close(other_us, "0.4", datetime(2026, 7, 10, 10, 0))

        result = self._resolve(
            year=2026, month=7, userBrokerId=other_us.user_broker_id)
        self.assertEqual(result.days, [])
        self.assertEqual(result.monthTrades, 0)
        self.assertAlmostEqual(result.monthPnlUsd, 0.0)

        account_ids = {str(a.id) for a in result.accounts}
        self.assertIn(str(self.us.user_broker_id), account_ids)
        self.assertNotIn(str(other_us.user_broker_id), account_ids)

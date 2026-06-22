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

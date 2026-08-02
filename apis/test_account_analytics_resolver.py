from datetime import date, datetime, timezone
from django.test import TestCase
from django.db import connection
from apis.models import User, UserBroker
from apis.schema.query.account_analytics import AccountAnalytics


class _Ctx:
    def __init__(self, user): self.user = user
class _Info:
    def __init__(self, user): self.context = _Ctx(user)


def _mk_broker_deals_table():
    with connection.cursor() as c:
        c.execute(
            "CREATE TABLE IF NOT EXISTS broker_deals ("
            "account_id varchar, deal_id varchar, position_id varchar, order_id varchar,"
            "symbol varchar, deal_type varchar, entry_type varchar, volume double precision,"
            "price double precision, profit double precision, commission double precision,"
            "swap double precision, deal_time timestamp, raw text, inserted_at timestamp)")


def _deal(c, acct, dt, profit, entry="DEAL_ENTRY_OUT", dtype="DEAL_TYPE_SELL"):
    c.execute("INSERT INTO broker_deals (account_id, deal_type, entry_type, profit, "
              "commission, swap, deal_time) VALUES (%s,%s,%s,%s,0,0,%s)",
              [acct, dtype, entry, profit, dt])


class ResolverTests(TestCase):
    def setUp(self):
        _mk_broker_deals_table()
        self.owner = User.objects.create(email="o@t.local", username="o")
        self.other = User.objects.create(email="x@t.local", username="x")
        self.broker = UserBroker.objects.create(user=self.owner, label="Acct",
                                                meta_account_id="ACC-1", api_key="k1")
        with connection.cursor() as c:
            _deal(c, "ACC-1", datetime(2026, 7, 1, 10, 0), 30.0)
            _deal(c, "ACC-1", datetime(2026, 7, 2, 10, 0), -10.0)

    def test_happy_path(self):
        res = AccountAnalytics.resolve_accountAnalytics(
            None, _Info(self.owner), userBrokerId=self.broker.id,
            fromDate=date(2026, 7, 1), toDate=date(2026, 7, 31))
        self.assertEqual(res.kpis.trades, 2)
        self.assertEqual(res.kpis.net_pnl_usd, 20.0)
        self.assertTrue(len(res.equity_curve) >= 2)

    def test_non_owner_rejected(self):
        from graphql import GraphQLError
        with self.assertRaises(GraphQLError):
            AccountAnalytics.resolve_accountAnalytics(
                None, _Info(self.other), userBrokerId=self.broker.id)

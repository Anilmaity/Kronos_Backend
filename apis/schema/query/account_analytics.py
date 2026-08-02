from datetime import date
import graphene
from graphql import GraphQLError
from django.db import connection
from apis.models import UserBroker
from apis.schema.utils import user_authenticate
from apis.schema.query._account_analytics_compute import compute_account_analytics


class EquityPoint(graphene.ObjectType):
    t = graphene.String()
    equityUsd = graphene.Float()


class AccountAnalyticsKpis(graphene.ObjectType):
    net_pnl_usd = graphene.Float()
    trades = graphene.Int()
    win_rate = graphene.Float()
    profit_factor = graphene.Float()
    avg_win_usd = graphene.Float()
    avg_loss_usd = graphene.Float()
    expectancy_usd = graphene.Float()
    max_drawdown_usd = graphene.Float()
    best_day_usd = graphene.Float()
    worst_day_usd = graphene.Float()
    avg_trades_per_day = graphene.Float()
    current_balance_usd = graphene.Float()


class AccountAnalyticsType(graphene.ObjectType):
    id = graphene.UUID()
    label = graphene.String()
    metaAccountId = graphene.String()
    isActive = graphene.Boolean()
    fromDate = graphene.Date()
    toDate = graphene.Date()
    kpis = graphene.Field(AccountAnalyticsKpis)
    equity_curve = graphene.List(EquityPoint)


class AccountAnalytics(graphene.ObjectType):
    accountAnalytics = graphene.Field(
        AccountAnalyticsType, userBrokerId=graphene.UUID(required=True),
        fromDate=graphene.Date(), toDate=graphene.Date())

    @user_authenticate
    def resolve_accountAnalytics(self, info, userBrokerId, fromDate=None, toDate=None):
        user = info.context.user
        try:
            broker = UserBroker.objects.get(id=userBrokerId)
        except UserBroker.DoesNotExist:
            raise GraphQLError("account not found")
        if not user.is_superuser and broker.user_id != user.id:
            raise GraphQLError("account not found")     # do not leak existence

        rows = []
        with connection.cursor() as c:
            c.execute(
                "SELECT deal_time, deal_type, entry_type, profit, commission, swap "
                "FROM broker_deals WHERE account_id = %s ORDER BY deal_time",
                [broker.meta_account_id])
            for dt, dtype, entry, profit, comm, swap in c.fetchall():
                rows.append({"deal_time": dt, "deal_type": dtype, "entry_type": entry,
                             "profit": profit, "commission": comm, "swap": swap})

        to_d = toDate or date.today()
        from_d = fromDate or (rows[0]["deal_time"].date() if rows else to_d)
        if from_d > to_d:
            raise GraphQLError("fromDate must be <= toDate")

        result = compute_account_analytics(rows, from_d, to_d)
        return AccountAnalyticsType(
            id=broker.id, label=broker.label or broker.meta_account_id or "unnamed",
            metaAccountId=broker.meta_account_id, isActive=broker.is_active,
            fromDate=from_d, toDate=to_d,
            kpis=AccountAnalyticsKpis(**result["kpis"]),
            equity_curve=[EquityPoint(t=t, equityUsd=v) for t, v in result["equity_curve"]],
        )

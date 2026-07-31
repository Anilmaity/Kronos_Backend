from datetime import date, datetime

import graphene
from graphql import GraphQLError
from django.db.models import F, Max, OuterRef, Subquery
from django.db.models.functions import Coalesce

from apis.models import Order, Position, UserBroker
from apis.schema.utils import user_authenticate

_USD_PER_PNL_UNIT = 100.0   # keep in sync with entry_manager / manager


class PnlDayType(graphene.ObjectType):
    date = graphene.Date()
    pnlUsd = graphene.Float()
    trades = graphene.Int()


class PnlAccountType(graphene.ObjectType):
    id = graphene.UUID()
    label = graphene.String()
    isActive = graphene.Boolean()


class PnlCalendarType(graphene.ObjectType):
    days = graphene.List(PnlDayType)
    monthPnlUsd = graphene.Float()
    monthTrades = graphene.Int()
    winDays = graphene.Int()
    lossDays = graphene.Int()
    accounts = graphene.List(PnlAccountType)


def _month_bounds(year: int, month: int):
    # NOTE: naive datetimes on purpose. USE_TZ=False in settings.py, so
    # DateTimeField values are stored and compared as naive wall-clock
    # (IST by platform quirk) - passing tz-aware bounds here raises
    # "SQLite backend does not support timezone-aware datetimes when
    # USE_TZ is False" (confirmed against the test DB) and would silently
    # mis-bucket days against Postgres too. Do NOT add tzinfo.
    start = datetime(year, month, 1)
    end = datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)
    return start, end


class PnlCalendar(graphene.ObjectType):
    pnlCalendar = graphene.Field(
        PnlCalendarType, year=graphene.Int(required=True),
        month=graphene.Int(required=True), userBrokerId=graphene.UUID())

    @user_authenticate
    def resolve_pnlCalendar(self, info, year, month, userBrokerId=None):
        if not 1 <= month <= 12:
            raise GraphQLError("month must be 1..12")
        if not 2020 <= year <= date.today().year + 1:
            raise GraphQLError("year out of range")
        start, end = _month_bounds(year, month)
        user = info.context.user

        exit_sq = (Order.objects.filter(position=OuterRef("pk"))
                   .exclude(condition="ENTRY").order_by()
                   .values("position")
                   .annotate(m=Max("created_at")).values("m"))
        qs = (Position.objects.filter(quantity=0)
              .annotate(exit_at=Coalesce(Subquery(exit_sq), F("modified_at")))
              .filter(exit_at__gte=start, exit_at__lt=end))
        # Scoping mirrors StrategyManagerState.resolve_managed_strategies:
        # non-superusers only ever see their own brokers' data; superusers see
        # everything. Without this, days/accounts leaked every user's PnL.
        if not user.is_superuser:
            qs = qs.filter(user_strategy__user_broker__user=user)
        if userBrokerId:
            qs = qs.filter(user_strategy__user_broker_id=userBrokerId)

        by_day: dict = {}
        for realized, exit_at in qs.values_list("realized_profit_loss", "exit_at"):
            d = exit_at.date()   # stored wall clock == IST day (platform quirk)
            agg = by_day.setdefault(d, {"pnl": 0.0, "n": 0})
            agg["pnl"] += float(realized or 0) * _USD_PER_PNL_UNIT
            agg["n"] += 1

        days = [PnlDayType(date=d, pnlUsd=round(v["pnl"], 2), trades=v["n"])
                for d, v in sorted(by_day.items())]

        accounts_qs = UserBroker.objects.filter(
            userstrategy__position__quantity=0).distinct()
        if not user.is_superuser:
            accounts_qs = accounts_qs.filter(user=user)
        accounts = [
            PnlAccountType(id=b.id,
                           label=b.label or b.meta_account_id or "unnamed",
                           isActive=b.is_active)
            for b in accounts_qs.order_by("label")
        ]
        return PnlCalendarType(
            days=days,
            monthPnlUsd=round(sum(v["pnl"] for v in by_day.values()), 2),
            monthTrades=sum(v["n"] for v in by_day.values()),
            winDays=sum(1 for v in by_day.values() if v["pnl"] > 0),
            lossDays=sum(1 for v in by_day.values() if v["pnl"] < 0),
            accounts=accounts,
        )

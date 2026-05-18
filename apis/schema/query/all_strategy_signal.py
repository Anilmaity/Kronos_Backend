import graphene
from datetime import datetime

from apis.models import StrategySignal
from apis.schema.utils import user_authenticate
from apis.schema.types.strategy_signal_type import StrategySignalType


class AllStrategySignal(graphene.ObjectType):
    allStrategySignal = graphene.List(
        StrategySignalType,
        strategyId=graphene.String(required=False),
        status=graphene.String(required=False),
        since=graphene.DateTime(required=False),
        until=graphene.DateTime(required=False),
        limit=graphene.Int(required=False, default_value=500),
    )

    @user_authenticate
    def resolve_allStrategySignal(
        self, info,
        strategyId=None, status=None,
        since=None, until=None,
        limit=500,
    ):
        qs = StrategySignal.objects.select_related("strategy").all()
        if strategyId:
            qs = qs.filter(strategy_id=strategyId)
        if status:
            qs = qs.filter(status=status)
        if since:
            qs = qs.filter(signal_at__gte=since)
        if until:
            qs = qs.filter(signal_at__lte=until)
        return qs.order_by("-signal_at")[: max(1, int(limit))]

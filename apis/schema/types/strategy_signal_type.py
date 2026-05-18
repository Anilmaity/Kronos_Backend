import graphene
from graphene_django import DjangoObjectType

from apis.models import StrategySignal


class StrategySignalType(DjangoObjectType):
    strategy_name = graphene.String()
    strategy_id = graphene.String()
    position_id = graphene.String()

    class Meta:
        model = StrategySignal
        fields = (
            "id",
            "created_at",
            "modified_at",
            "symbol",
            "side",
            "entry_price",
            "stop_loss",
            "take_profit",
            "reason",
            "status",
            "rejection_reason",
            "signal_at",
        )

    def resolve_strategy_name(self, info):
        return self.strategy.name if self.strategy_id else None

    def resolve_strategy_id(self, info):
        return str(self.strategy_id) if self.strategy_id else None

    def resolve_position_id(self, info):
        return str(self.position_id) if self.position_id else None

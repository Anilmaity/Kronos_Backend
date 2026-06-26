import graphene
from graphene_django import DjangoObjectType

from apis.models import StrategySignal


class StrategySignalType(DjangoObjectType):
    strategy_name = graphene.String()
    strategy_id = graphene.String()
    position_id = graphene.String()
    # reason / rejection_reason are CharField(blank=True) with NO null=True, so the
    # auto-mapped GraphQL fields are non-null (String!). But rows written outside
    # Django (raw SQL via the telegram bot, SQLAlchemy via entry_manager, the
    # backfill command) can hold actual NULLs, which made graphene raise
    # "Cannot return null for non-nullable field". Declare them nullable and
    # coalesce NULL -> "" so the query never errors and consumers get a string.
    reason = graphene.String()
    rejection_reason = graphene.String()

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

    def resolve_reason(self, info):
        return self.reason or ""

    def resolve_rejection_reason(self, info):
        return self.rejection_reason or ""

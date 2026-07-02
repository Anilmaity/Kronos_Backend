from datetime import datetime

import graphene
from graphene_django import DjangoObjectType
from pytz import timezone

from apis.models import ManagedStrategy
# Importing UserStrategyType registers it with graphene-django so the
# `user_strategy` relation on ManagedStrategyType resolves to the full
# UserStrategyType (positions, totals, brokerName, ...) instead of a stub.
from apis.schema.types.user_strategy_type import UserStrategyType  # noqa: F401

kolkata = timezone("Asia/Kolkata")


class ManagedStrategyType(DjangoObjectType):
    strategyName = graphene.String()
    todayPnl = graphene.Float()
    openPositions = graphene.Int()

    class Meta:
        model = ManagedStrategy
        fields = "__all__"

    def resolve_strategyName(self, info):
        return self.user_strategy.strategy.name

    def resolve_todayPnl(self, info):
        """Sum of today's (IST, matching the rest of the API) realized P&L
        over this managed UserStrategy's positions."""
        today = datetime.now(tz=kolkata).date()
        return float(
            sum(
                p.realized_profit_loss
                for p in self.user_strategy.position_set.filter(
                    created_at__date=today
                )
            )
        )

    def resolve_openPositions(self, info):
        # "Open" = quantity != 0, the definition used everywhere else in this
        # codebase (active_positions_count, archive guard) — shorts included.
        return self.user_strategy.position_set.exclude(quantity=0).count()

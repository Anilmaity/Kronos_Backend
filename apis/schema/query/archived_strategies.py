import graphene

from apis.models import UserStrategy
from apis.schema.utils import user_authenticate
from apis.schema.types.user_strategy_type import UserStrategyType


class ArchivedStrategies(graphene.ObjectType):
    archived_strategies = graphene.List(UserStrategyType)

    @user_authenticate
    def resolve_archived_strategies(self, info):
        return UserStrategy.objects.filter(
            user_broker__user=info.context.user, archived=True
        ).order_by("-created_at")

import graphene

from apis.models import *
from apis.schema.utils import user_authenticate
from apis.schema.types.strategy_type import StrategyType


class AllStrategy(graphene.ObjectType):
    allStrategy = graphene.List(StrategyType)


    @user_authenticate
    def resolve_allStrategy(self, info):
        # FIXME should we show all the strategies? to all users
        return Strategy.objects.all().order_by("-created_at")

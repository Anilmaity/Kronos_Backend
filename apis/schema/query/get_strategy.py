import graphene

from apis.models import *
from apis.schema.utils import user_authenticate
from apis.schema.types.strategy_type import StrategyType


class GetStrategy(graphene.ObjectType):
    getStrategy = graphene.Field(StrategyType, id=graphene.String())


    @user_authenticate
    def resolve_getStrategy(self, info, id):
        return Strategy.objects.get(id=id)


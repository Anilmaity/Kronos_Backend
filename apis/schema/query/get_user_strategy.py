import graphene
from graphql import GraphQLError

from apis.models import *
from apis.schema.types.user_strategy_type import UserStrategyType
from apis.schema.utils import *


class GetUserStrategy(graphene.ObjectType):
    get_user_positions = graphene.Field(UserStrategyType,id=graphene.String())

    @user_authenticate
    def resolve_get_user_strategy(self,info,id):
        return UserStrategy.objects.get(id=id)


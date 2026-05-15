
import graphql_jwt

import graphene

from graphql_jwt.shortcuts import get_token

from apis.models import UserStrategy , Strategy, UserBroker
from apis.schema.utils import admin_authenticate
from apis.schema.types.user_strategy_type import UserStrategyType


class PauseStrategy(graphene.Mutation):
    Response = graphene.String()
    Strategy = graphene.Field(UserStrategyType)

    class Arguments:
        id = graphene.String(required=True)

    @admin_authenticate
    def mutate(self, info, id, ):
        try:
            strategy = Strategy.objects.get(id=id)
            strategy.is_active = not(strategy.is_active)
            strategy.save()
            return PauseStrategy(Response="Success", Strategy=strategy)
        except UserStrategy.DoesNotExist:
            return PauseStrategy(
                Response="Strategy Does Not Exist", Strategy=None
            )



import graphql_jwt

import graphene

from graphql_jwt.shortcuts import get_token

from apis.models import UserStrategy
from apis.schema.utils import user_authenticate
from apis.schema.types.user_strategy_type import UserStrategyType


class SetUserStrategyQuantity(graphene.Mutation):
    Response = graphene.String()
    UserStrategy = graphene.Field(UserStrategyType)

    class Arguments:
        user_strategy_id = graphene.String(required=True)
        quantity = graphene.Int(required=True)

    @user_authenticate
    def mutate(self, info, user_strategy_id, quantity):
        try:
            if info.context.user.is_superuser:
                userstrategy = UserStrategy.objects.get(id=user_strategy_id)
            else:
                userstrategy = UserStrategy.objects.get(
                    user_broker__user=info.context.user, id=user_strategy_id
                )

            userstrategy.multiplyer = quantity
            userstrategy.save()
            return SetUserStrategyQuantity(
                Response="Success", UserStrategy=userstrategy
            )
        except UserStrategy.DoesNotExist:
            return SetUserStrategyQuantity(
                Response="Strategy Does Not Exist", UserStrategy=None
            )
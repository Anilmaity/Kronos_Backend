
import graphql_jwt

import graphene

from graphql_jwt.shortcuts import get_token

from apis.models import UserStrategy
from apis.schema.utils import user_authenticate
from apis.schema.types.user_strategy_type import UserStrategyType


class ChangeStrategyStatus(graphene.Mutation):
    Response = graphene.String()
    UserStrategy = graphene.Field(UserStrategyType)

    class Arguments:
        user_strategy_id = graphene.String(required=True)
        status = graphene.Boolean(required=True)

    @user_authenticate
    def mutate(self, info, user_strategy_id, status):
        try:
            if info.context.user.is_superuser:
                userstrategy = UserStrategy.objects.get(id=user_strategy_id)
            else:
                userstrategy = UserStrategy.objects.get(
                    user_broker__user=info.context.user, id=user_strategy_id
                )
            userstrategy.active = status
            userstrategy.save()
            return ChangeStrategyStatus(Response="Success", UserStrategy=userstrategy)
        except UserStrategy.DoesNotExist:
            return ChangeStrategyStatus(
                Response="Strategy Does Not Exist", UserStrategy=None
            )

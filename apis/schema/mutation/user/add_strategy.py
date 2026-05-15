
import graphql_jwt

import graphene

from graphql_jwt.shortcuts import get_token

from apis.models import UserStrategy , Strategy, UserBroker
from apis.schema.utils import user_authenticate
from apis.schema.types.user_strategy_type import UserStrategyType


class AddStrategy(graphene.Mutation):
    UserStrategy = graphene.Field(UserStrategyType)
    Response = graphene.String()

    class Arguments:
        strategy_id = graphene.String(required=True)
        user_broker_id = graphene.String(required=True)
        quantity = graphene.Int(required=False)

    @user_authenticate
    def mutate(self, info, strategy_id, user_broker_id, quantity=1):
        try:
            userstrategy = UserStrategy.objects.get(
                user_broker_id=user_broker_id, strategy_id=strategy_id
            )
            return AddStrategy(UserStrategy=userstrategy, Response="Strategy Already Exists")
        except UserStrategy.DoesNotExist:
            try:
                strategy = Strategy.objects.get(id=strategy_id)
                userbroker = UserBroker.objects.get(id=user_broker_id)
                userstrategy = UserStrategy.objects.create(
                    user_broker=userbroker,
                    strategy=strategy,
                    name=(strategy.name),
                    multiplyer=quantity,
                    broker_name=userbroker.broker.name,
                )

                return AddStrategy(UserStrategy=userstrategy, Response="Success")
            except (UserBroker.DoesNotExist, Strategy.DoesNotExist):
                return AddStrategy(
                    UserStrategy=None, Response="Broker or Strategy Does Not Exist"
                )

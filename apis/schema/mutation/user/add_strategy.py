import graphene

from apis.models import UserStrategy, Strategy, UserBroker
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
            if info.context.user.is_superuser:
                userbroker = UserBroker.objects.get(id=user_broker_id)
            else:
                userbroker = UserBroker.objects.get(
                    id=user_broker_id, user=info.context.user
                )
        except UserBroker.DoesNotExist:
            return AddStrategy(UserStrategy=None, Response="Account does not exist")

        try:
            strategy = Strategy.objects.get(id=strategy_id)
        except Strategy.DoesNotExist:
            return AddStrategy(UserStrategy=None, Response="Strategy does not exist")

        existing = UserStrategy.objects.filter(
            user_broker=userbroker, strategy=strategy
        ).first()
        if existing:
            return AddStrategy(
                UserStrategy=existing, Response="Strategy Already Exists"
            )

        userstrategy = UserStrategy.objects.create(
            user_broker=userbroker,
            strategy=strategy,
            name=strategy.name,
            multiplyer=quantity,
            is_active=True,
            deployed=True,
        )
        return AddStrategy(UserStrategy=userstrategy, Response="Success")


import graphene

from apis.models import UserStrategy
from apis.schema.utils import user_authenticate
from apis.schema.types.user_strategy_type import UserStrategyType


class SetUserStrategyMultiplier(graphene.Mutation):
    Response = graphene.String()
    UserStrategy = graphene.Field(UserStrategyType)

    class Arguments:
        user_strategy_id = graphene.String(required=True)
        multiplier = graphene.Int(required=True)

    @user_authenticate
    def mutate(self, info, user_strategy_id, multiplier):
        if multiplier < 1:
            return SetUserStrategyMultiplier(
                Response="Multiplier must be >= 1", UserStrategy=None
            )
        try:
            if info.context.user.is_superuser:
                userstrategy = UserStrategy.objects.get(id=user_strategy_id)
            else:
                userstrategy = UserStrategy.objects.get(
                    user_broker__user=info.context.user, id=user_strategy_id
                )

            userstrategy.multiplyer = multiplier
            userstrategy.save()
            return SetUserStrategyMultiplier(
                Response="Success", UserStrategy=userstrategy
            )
        except UserStrategy.DoesNotExist:
            return SetUserStrategyMultiplier(
                Response="Strategy Does Not Exist", UserStrategy=None
            )

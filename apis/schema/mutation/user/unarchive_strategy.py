import graphene

from apis.models import UserStrategy
from apis.schema.utils import user_authenticate
from apis.schema.types.user_strategy_type import UserStrategyType


class UnarchiveStrategy(graphene.Mutation):
    """Restore an archived strategy to the dashboard.

    Sets archived=False only. Does NOT redeploy — the strategy stays stopped
    and must be re-deployed explicitly through the normal flow.
    """

    Response = graphene.String()
    UserStrategy = graphene.Field(UserStrategyType)

    class Arguments:
        user_strategy_id = graphene.String(required=True)

    @user_authenticate
    def mutate(self, info, user_strategy_id):
        try:
            if info.context.user.is_superuser:
                us = UserStrategy.objects.get(id=user_strategy_id)
            else:
                us = UserStrategy.objects.get(
                    user_broker__user=info.context.user, id=user_strategy_id
                )
        except UserStrategy.DoesNotExist:
            return UnarchiveStrategy(
                Response="Strategy Does Not Exist", UserStrategy=None
            )

        us.archived = False
        us.save()
        return UnarchiveStrategy(Response="Success", UserStrategy=us)

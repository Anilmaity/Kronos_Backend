import graphene

from apis.models import UserStrategy, Position
from apis.schema.utils import user_authenticate
from apis.schema.types.user_strategy_type import UserStrategyType


class ArchiveStrategy(graphene.Mutation):
    """Manually archive a user strategy.

    Archiving auto-stops the strategy (deployed=False, is_active=False) so a
    hidden strategy can never keep trading. It is blocked while any position is
    open (quantity != 0) to avoid orphaning a live broker trade.
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
            return ArchiveStrategy(
                Response="Strategy Does Not Exist", UserStrategy=None
            )

        if Position.objects.filter(user_strategy=us).exclude(quantity=0).exists():
            return ArchiveStrategy(
                Response="Cannot archive: open positions exist. Exit the strategy first.",
                UserStrategy=us,
            )

        us.archived = True
        us.deployed = False
        us.is_active = False
        us.save()
        return ArchiveStrategy(Response="Success", UserStrategy=us)

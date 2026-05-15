import graphene
from apis.models import Strategy, Action
from apis.schema.utils import admin_authenticate
from apis.schema.types.strategy_type import StrategyType


class DeleteStrategyAction(graphene.Mutation):
    Response = graphene.String()

    class Arguments:
        id = graphene.String(required=True)

    @admin_authenticate
    def mutate(self, info, id):
        Action.objects.filter(id=id).delete()
        return DeleteStrategyAction(Response="Action Deleted Successfully")


class PauseStrategy(graphene.Mutation):
    Response = graphene.String()
    Strategy = graphene.Field(StrategyType)

    class Arguments:
        id = graphene.String(required=True)

    @admin_authenticate
    def mutate(self, info, id):
        try:
            strategy = Strategy.objects.get(id=id)
            strategy.active = not (strategy.active)
            strategy.save()
            return PauseStrategy(
                Response="Strategy Paused Successfully", Strategy=strategy
            )
        except Strategy.DoesNotExist:
            return PauseStrategy(Response="Strategy Does Not Exist", Strategy=None)


import graphene
from apis.models import Strategy, CurrencyPair, Action
from apis.schema.utils import admin_authenticate
from apis.schema.types.action_type import ActionType


class AddStrategyAction(graphene.Mutation):
    Response = graphene.String()
    Action = graphene.Field(ActionType)

    class Arguments:
        strtegy_id = graphene.String(required=True)
        action_type = graphene.String(required=True)
        value = graphene.Float(required=True)
        create_trigger = graphene.Boolean(required=True)
        quantity = graphene.Float(required=False)
        trigger_type = graphene.String(required=True)

    @admin_authenticate
    def mutate(self, info, strtegy_id, action_type, value, create_trigger, quantity , trigger_type):
        try:
            strategy = Strategy.objects.get(id=strtegy_id)
            if action_type == "TARGET" or action_type == "STOPLOSS":
                action = Action.objects.create(
                    strategy=strategy,
                    action_type=action_type,
                    trigger_value=value,
                    create_trigger=False, # not to place limit order
                    trigger_type=trigger_type,
                    quantity=quantity,
                    action="SELL",
                )
                return AddStrategyAction(Action=action, Response="Success")
            else:
                return AddStrategyAction(
                    Response="Invalid Action Type possible values are TARGET or STOPLOSS"
                )

        except Strategy.DoesNotExist:
            return AddStrategyAction(Response="Strategy Does Not Exist")

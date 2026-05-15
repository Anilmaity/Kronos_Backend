import graphene
from apis.models import Strategy, CurrencyPair, Action
from apis.schema.utils import admin_authenticate
from apis.schema.types.action_type import ActionType


class UpdateStrategyAction(graphene.Mutation):
    Response = graphene.String()
    Action = graphene.Field(ActionType)

    class Arguments:
        id = graphene.String(required=True)
        points = graphene.Float(required=False)
        create_trigger = graphene.Boolean(required=False)
        quantity = graphene.Float(required=False)
        action_type = graphene.String(required=False)

    @admin_authenticate
    def mutate(self, info, id, points=None, create_trigger=None, quantity=None):
        try:
            Action.objects.get(id=id)
            action = Action.objects.get(id=id)
            if points:
                action.trigger_value = points
            if create_trigger:
                action.create_trigger = create_trigger
            if quantity:
                action.quantity = quantity

            action.save()

        except Action.DoesNotExist:
            return UpdateStrategyAction(Response="Action Does Not Exist")

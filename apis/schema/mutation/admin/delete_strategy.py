import graphene
from apis.models import Strategy, CurrencyPair
from apis.schema.utils import admin_authenticate

class DeleteStrategy(graphene.Mutation):
    Response = graphene.String()

    class Arguments:
        id = graphene.String(required=True)

    @admin_authenticate
    def mutate(self, info, id):
        Strategy.objects.filter(id=id).delete()
        return DeleteStrategy(Response="Strategy Deleted Successfully")
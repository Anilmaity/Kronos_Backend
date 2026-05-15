import graphene
from apis.models import Strategy, CurrencyPair
from apis.schema.utils import admin_authenticate


class CreateStrategy(graphene.Mutation):
    Response = graphene.String()

    class Arguments:
        name = graphene.String(required=True)
        currency_id = graphene.String(required=True)
        capital = graphene.Float(required=True)
        monthly_return = graphene.Float(required=True)
        drawdown = graphene.Float(required=True)
        description = graphene.String(required=True)
        interval = graphene.String(required=True)
        entry_quantity = graphene.Float(required=True)

    @admin_authenticate
    def mutate(
        self,
        info,
        name,
        currency_id,
        capital,
        monthly_return,
        drawdown,
        description,
        interval,
        entry_quantity,
    ):
        try:
            strategy = Strategy.objects.get(name=name)
            return CreateStrategy(Response="Strategy Already Exists")
        except Strategy.DoesNotExist:

            try:
                currencypair = CurrencyPair.objects.get(id=currency_id)

                strategy = Strategy.objects.create(
                    name=name,
                    currencypair=currencypair,
                    capital=capital,
                    monthly_return=monthly_return,
                    drawdown=drawdown,
                    description=description,
                    interval=interval,
                    entry_quantity=entry_quantity,
                    is_active=False
                )
                return CreateStrategy(Response="Success")
            except CurrencyPair.DoesNotExist:
                return CreateStrategy(Response="Index Does Not Exist")

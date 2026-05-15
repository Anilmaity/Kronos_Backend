
import graphene
from graphene_django import DjangoObjectType

from apis.models import (Action, Order, Position, CurrencyPair,
                               Signal, Strategy, Trigger)


class CurrencyPairType(DjangoObjectType):
    symbol = graphene.String()
    name = graphene.String()
    exchange = graphene.String()
    segment = graphene.String()

    def resolve_symbol(self, info, ):
        return (self.symbol)

    def resolve_name(self, info, ):
        return (self.name)

    def resolve_exchange(self, info, ):
        return (self.exchange)

    def resolve_segment(self, info, ):
        return (self.segment)


    class Meta:
        model = CurrencyPair
        exclude = ("strategy_set",)


#####################################################################   LIBRARIES   ########################################################################
import datetime

import graphene
from graphene_django import DjangoObjectType

from apis.models import (Action, Signal)

##############################################################################################################################################################

class SignalType(DjangoObjectType):
    x = graphene.Time()
    y = graphene.String()
    symbol = graphene.String()

    def resolve_symbol(self, info, ):
        return (self.strategy.currencypair.symbol)
    class Meta:
        model = Signal
        exclude = ("strategy",)

    def resolve_y(
        self,
        info,
    ):
        return self.price

    def resolve_x(
        self,
        info,
    ):
        localdatetime = self.created_at
        localdatetime = localdatetime.strftime("%Y-%m-%d %H:%M:%S")
        localdatetime = datetime.datetime.strptime(localdatetime, "%Y-%m-%d %H:%M:%S")
        return localdatetime.time()

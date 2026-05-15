#####################################################################   LIBRARIES   ########################################################################
from datetime import datetime, timedelta

from django.db.models import Sum

from apis.schema.types.action_type import ActionType
from apis.schema.types.signal_type import SignalType
import graphene
from graphene_django import DjangoObjectType

from apis.models import (Strategy, Position)
import pytz


kolkata = pytz.timezone("Asia/Kolkata")
##############################################################################################################################################################


class AnalyticsType(graphene.ObjectType):
    labels = graphene.List(graphene.String)
    values = graphene.List(graphene.Decimal)

class StrategyType(DjangoObjectType):
    symbol = graphene.String()
    today_signals = graphene.List(SignalType)
    actions = graphene.List(ActionType)
    name = graphene.String()
    description = graphene.String()
    monthlyReturn = graphene.String()
    drawdown = graphene.String()
    interval = graphene.String()
    signals = graphene.List(SignalType , date = graphene.String())
    analytics = graphene.Field(AnalyticsType, cumulative = graphene.Boolean() , includeDummy = graphene.Boolean() , type = graphene.String())

    label = graphene.String()

    def resolve_label(self, info):
        return self.name









    def resolve_signals(self, info, date=None):
        if date:
            return self.signal_set.filter(created_at__date=date).order_by('created_at')
        else:
            return self.signal_set.filter(created_at__date=datetime.now(tz=kolkata).date()).order_by('created_at')



    def resolve_interval(self, info, ):
        return (self.interval)

    def resolve_description(self, info, ):
        return (self.description)




    def resolve_name(self, info, ):
        return (self.name)

    class Meta:
        model = Strategy
        exclude = (
            "json_data",
            "signal_set",
            "userstrategy_set",
            "action_set",
        )

    def resolve_today_signals(self, info, ):
        if info.context.user.is_superuser:
            return self.signal_set.filter(created_at__date=datetime.now(tz = kolkata).date()).order_by('created_at')
        else:
            return []
    def resolve_symbol(self, info, ):
        return (self.currencypair.symbol)



    def resolve_monthlyReturn(self, info, ):
        return (self.monthly_return)

    def resolve_drawdown(self, info, ):
        return (self.drawdown)
    def resolve_actions(
        self,
        info,
    ):
        return self.action_set.all().order_by("-created_at")


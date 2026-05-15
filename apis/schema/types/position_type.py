#####################################################################   LIBRARIES   ########################################################################
import datetime

import graphene
from graphene_django import DjangoObjectType

from apis.models import (Position)
from apis.schema.types.order_type import OrderType
from apis.schema.types.trigger_type import TriggerType


##############################################################################################################################################################




class PositionType(DjangoObjectType):
    Orders = graphene.List(OrderType)
    ltp = graphene.Float()
    profit_loss = graphene.Float()
    profit_loss_percentage = graphene.Float()
    triggers = graphene.List(TriggerType)
    totalValue = graphene.Float()

    class Meta:
        model = Position
        exclude = ("order_set", "trigger_set", "user_strategy")

    def resolve_ltp(self, info):
        return self.currencypair.ltp


    def resolve_totalValue(self, info):
        return self.avg_buy_price * self.quantity *100

    def resolve_profit_loss(self, info):
        return round((float(self.realized_profit_loss) + (float(self.currencypair.ltp) - float(self.avg_buy_price))* float(self.quantity))*100,2)

    def resolve_profit_loss_percentage(self, info):
        return round(float(self.realized_profit_loss) + (float(self.currencypair.ltp) - float(self.avg_buy_price))* float(self.quantity),2) / (float(self.avg_buy_price) * float(self.quantity)) * 100


    def resolve_Orders(
        self,
        info,
    ):
        orders_by_created_at = self.order_set.all().order_by("-created_at")

        # Retrieve orders ordered by 'condition' in descending order
        self.order_set.all().order_by("condition")

        # Combine the two querysets into a single queryset

        return orders_by_created_at

    def resolve_triggers(self,info):
        return self.trigger_set.all()


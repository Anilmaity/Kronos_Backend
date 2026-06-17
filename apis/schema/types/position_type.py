#####################################################################   LIBRARIES   ########################################################################
import datetime

import graphene
from graphene_django import DjangoObjectType

from apis.models import (Position)
from apis.schema.types.order_type import OrderType
from apis.schema.types.trigger_type import TriggerType
from apis.schema.types.pnl import position_pnl, position_notional, position_pnl_pct


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
        # Notional at entry — use whichever side was opened (long: avg_buy_price,
        # short: avg_sell_price). Long-only `avg_buy_price * qty` showed 0 for shorts.
        return position_notional(self.quantity, self.avg_buy_price, self.avg_sell_price)

    def resolve_profit_loss(self, info):
        # Directional realized + unrealized PnL. The old long-only formula priced a
        # short against avg_buy_price == 0, inflating PnL to ~ the entry price ("4K").
        return position_pnl(self.realized_profit_loss, self.currencypair.ltp,
                            self.quantity, self.avg_buy_price, self.avg_sell_price)

    def resolve_profit_loss_percentage(self, info):
        return position_pnl_pct(self.realized_profit_loss, self.currencypair.ltp,
                                self.quantity, self.avg_buy_price, self.avg_sell_price)


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


#####################################################################   LIBRARIES   ########################################################################

from datetime import datetime
import graphene
from graphene_django import DjangoObjectType
from pytz import timezone


from apis.models import (UserStrategy)
from apis.schema.types.position_type import PositionType

kolkata = timezone("Asia/Kolkata")

##############################################################################################################################################################


class UserStrategyType(DjangoObjectType):
    positions = graphene.List(PositionType, date=graphene.Date(), userstrategy_ids=graphene.List(graphene.UUID))
    dailypositions = graphene.List(PositionType, date=graphene.String())
    brokerName = graphene.String()
    total_profit_loss = graphene.Float(date=graphene.Date(), userstrategy_ids=graphene.List(graphene.UUID))
    total_position_count = graphene.Int(date=graphene.Date(), userstrategy_ids=graphene.List(graphene.UUID))
    active_positions_count = graphene.Int(date=graphene.Date(), userstrategy_ids=graphene.List(graphene.UUID))
    name = graphene.String()



    class Meta:
        model = UserStrategy
        exclude = ( "position_set",)
    def resolve_name(self, info):
        return (self.strategy.name)
    def resolve_total_position_count(self, info ,date = "", userstrategy_ids=[]):
        if len(userstrategy_ids) > 0:
            positions = self.position_set.filter(user_strategy__in=userstrategy_ids, date=date).order_by("-created_at")
        elif date != "":
            positions = self.position_set.filter(created_at__date=date).order_by("-created_at")
        else:
            positions = self.position_set.filter(created_at__date=datetime.now(tz=kolkata).date()).order_by("-created_at")

        return positions.count()

    def resolve_active_positions_count(self, info ,date = "", userstrategy_ids=[]):
        if len(userstrategy_ids) > 0:
            positions = self.position_set.filter(user_strategy__in=userstrategy_ids, date=date).order_by("-created_at")
        elif date != "":
            positions = self.position_set.filter(created_at__date=date).order_by("-created_at")
        else:
            positions = self.position_set.filter(created_at__date=datetime.now(tz=kolkata).date()).order_by("-created_at")
        return positions.exclude(quantity=0).count()

    def resolve_total_profit_loss(self, info ,date = "", userstrategy_ids=[]):

        if date != "":
            positions = self.position_set.filter(created_at__date=date).order_by("-created_at").all()
        else:
            positions = self.position_set.filter(created_at__date=datetime.now(tz=kolkata).date()).order_by("-created_at").all()

        profit_loss = sum([(float(position.currencypair.ltp) - float(position.avg_buy_price))*float(position.quantity) + float(position.realized_profit_loss) for position in positions])
        if profit_loss:
            return profit_loss
        else:
            return 0


    # get specific broker name
    def resolve_brokerName(self, info):
        return self.user_broker.broker.name

    # fetching position values for user

    def resolve_positions(self, info, date = "", userstrategy_ids=[]):
        # give all position value of that user
        # print(date)
        if date != "":
            positions = self.position_set.filter(created_at__date=date,user_strategy__in=userstrategy_ids).order_by("-created_at")
        else:
            positions = self.position_set.filter(created_at__date=datetime.now(tz=kolkata,).date(),user_strategy__in=userstrategy_ids).order_by("-created_at")

        return positions

    # fetching daily positions
    def resolve_dailypositions(self, info ):

        positions = self.position_set.all().order_by("-date")
        unique_date = []
        # use set function here
        for position in positions:
            if position.date not in unique_date:
                unique_date.append(position.date)

        daily_positions = []
        for date in unique_date:
            same_days_position = self.position_set.filter(created_at__date=date).order_by("-id")
            for position in same_days_position:
                same_days_position[0].profit_loss = position.profit_loss

            daily_positions.append(same_days_position[0])

        return daily_positions

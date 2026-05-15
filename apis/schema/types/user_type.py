#####################################################################   LIBRARIES   ########################################################################

from datetime import datetime
import graphene
from django.db.models import Sum
from graphene_django import DjangoObjectType
from pytz import timezone


from apis.models import (Position, Strategy, User,UserStrategy)
from apis.schema.types.position_type import PositionType
from apis.schema.types.strategy_type import StrategyType
from apis.schema.types.user_broker_type import UserBrokerType
from apis.schema.types.user_strategy_type import UserStrategyType

kolkata = timezone("Asia/Kolkata")
##############################################################################################################################################################



class UserType(DjangoObjectType):
    userbrokers = graphene.List(
        UserBrokerType,
        include_dummy=graphene.Boolean(),
        userbrokers=graphene.List(graphene.UUID),
    )
    reports_positions = graphene.List(
        PositionType,
        from_date=graphene.Date(),
        to_date=graphene.Date(),
        strategies=graphene.List(graphene.UUID),
        userbrokers=graphene.List(graphene.UUID),
        include_dummy=graphene.Boolean(),
    )
    strategies = graphene.List(StrategyType)
    userstrategys = graphene.List(UserStrategyType)
    first_name = graphene.String()
    last_name = graphene.String()

    def resolve_first_name(self, info):
        return (self.first_name)

    def resolve_last_name(self, info):
        return (self.last_name)



    class Meta:
        model = User
        exclude = ("userbroker_set", "password", "email", "username")

    def resolve_userstrategys(self, info):
        return UserStrategy.objects.filter(user_broker__user=self).order_by("-created_at")




    def resolve_strategies(
            self,
            info,
    ):
        return Strategy.objects.filter(userstrategy__user_broker__user=self).distinct()

    def resolve_reports_positions(
            self,
            info,
            from_date=None,
            to_date=None,
            strategies=None,
            userbrokers=None,
            include_dummy=False,
    ):
        if from_date != None and to_date != None:
            positions = Position.objects.filter(
                user_strategy__user_broker__user=self,
                date__gte=from_date,
                date__lte=to_date,
            )
        elif from_date != None:
            positions = Position.objects.filter(
                user_strategy__user_broker__user=self, date__gte=from_date
            )
        elif to_date != None:
            positions = Position.objects.filter(
                user_strategy__user_broker__user=self, date__lte=to_date
            )
        else:
            positions = Position.objects.filter(user_strategy__user_broker__user=self)

        if strategies != None:
            positions = positions.filter(user_strategy__strategy__in=strategies)
        if userbrokers != None:
            positions = positions.filter(user_strategy__user_broker__in=userbrokers)
        if include_dummy == False:
            positions = positions.exclude(user_strategy__user_broker__broker__name="Dummy")

        unique_positions = []
        # having same symbol add quantity and pnl
        for position in positions:
            if position.symbol not in [
                unique_position.symbol for unique_position in unique_positions
            ]:
                unique_positions.append(position)
            else:
                for unique_position in unique_positions:
                    if unique_position.symbol == position.symbol:
                        unique_position.total_buy_quantity += (
                            position.total_buy_quantity
                        )
                        unique_position.avg_buy_price = position.avg_buy_price
                        unique_position.profit_loss += position.profit_loss
                        unique_position.avg_sell_price += position.avg_buy_price

        for position in unique_positions:
            position.profit_loss = round(position.profit_loss, 2)
            position.avg_buy_price = round(position.avg_buy_price, 2)
            position.avg_sell_price = round(
                position.avg_buy_price
                + position.profit_loss / position.total_buy_quantity,
                2,
            )

        return unique_positions

    def resolve_userbrokers(self, info, include_dummy=True, userbrokers=[]):


        if len(userbrokers) != 0:
            userbrokers = self.userbroker_set.filter(id__in=userbrokers).order_by("-created_at")
        else:
            userbrokers = self.userbroker_set.order_by("-created_at")

        if include_dummy == False:
            userbrokers = userbrokers.exclude(broker__name="Dummy")
        return userbrokers


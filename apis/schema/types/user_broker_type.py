#####################################################################   LIBRARIES   ########################################################################
from datetime import datetime, timedelta


import graphene
from django.db.models import Sum
from graphene_django import DjangoObjectType
from pytz import timezone


from apis.models import (Position,
                                UserBroker,
                                models)
from apis.schema.types.position_type import PositionType
from apis.schema.types.strategy_type import AnalyticsType
from apis.schema.types.user_strategy_type import UserStrategyType

kolkata = timezone("Asia/Kolkata")

##############################################################################################################################################################



class UserBrokerType(DjangoObjectType):
    """ "Get daily, weekly and"""

    userstrategys = graphene.List(
        UserStrategyType, strategies=graphene.List(graphene.UUID)
    )
    dailypnl = graphene.List(PositionType)
    marginAvailable = graphene.String()
    accountHolderName = graphene.String()
    accountValueOnStartingOfMonth = graphene.String()
    marginUsed = graphene.String()
    status = graphene.String()
    label = graphene.String()

    def resolve_label(self, info):
        return self.unique_code





    def resolve_status(self, info):
        return (self.status)


    def resolve_today_actual_total_profit_loss(self, info):
        broker_positions = self.userbrokerposition_set.filter(
            created_at__date=datetime.now(tz=kolkata).date()
        ).aggregate(Sum("profit_loss"))["profit_loss__sum"]

        if broker_positions:
            return broker_positions
        else:
            return 0



    def resolve_marginUsed(self, info):
        return (self.margin_used)





    def resolve_marginAvailable(self, info):
        return (self.margin_available)


    def resolve_strategy_positions(self, info):
        positions = (
            Position.objects.filter(
                created_at__date=datetime.now(tz=kolkata).date(),
            )
            .exclude(quantity=0)
            .order_by("-id")
        )
        return positions




    # get positions of
    def get_positions_query(self):
        positions_query = (
            Position.objects.filter(user_strategy__user_broker=self.id)
            .values("user_strategy__user_broker__client_code")
            .annotate(
                overall_profit_loss=Sum(
                    "profit_loss", output_field=models.DecimalField()
                )
            )
        )
        return positions_query


    def resolve_dailypnl(self, info):
        userstrategy = self.userstrategy_set.all()
        positions = []

        for us in userstrategy:
            positions.extend(us.position_set.all().order_by("-id"))

        unique_date = []
        for position in positions:
            if position.date not in unique_date:
                unique_date.append(position.date)

        daily_positions = []
        for date in unique_date:
            same_days_position = []
            for position in positions:
                if position.date == date:
                    same_days_position.append(position)

            same_days_position[0].profit_loss = sum(
                position.profit_loss for position in same_days_position
            )

            daily_positions.append(same_days_position[0])

        daily_positions.sort(key=lambda x: x.date, reverse=True)
        return daily_positions

    def resolve_userstrategys(self, info, strategies=[]):
        if len(strategies) > 0:
            return self.userstrategy_set.filter(strategy__in=strategies).order_by("-created_at")
        else:
            return self.userstrategy_set.all().order_by("-created_at")

    class Meta:
        model = UserBroker
        exclude = ("user", "userstrategy_set", "order_set")

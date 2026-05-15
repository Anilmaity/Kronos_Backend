import graphene
from graphql import GraphQLError

from apis.models import *
from apis.schema.utils import user_authenticate


class GetHeatMap(graphene.ObjectType):
    getheatmap = graphene.JSONString(fromdate=graphene.Date(), todate=graphene.Date())

    @user_authenticate
    def resolve_getheatmap(self, info, fromdate=None, todate=None):
        user = info.context.user
        positions = []
        userbrokers = UserBroker.objects.exclude(broker__name="Dummy").filter(
            user=user
        )  # getting all user broker excluding dummy data

        # getting strategy of particualr broker account
        for userbroker in userbrokers:
            userstrategys = userbroker.userstrategy_set.all()
            for userstrategy in userstrategys:
                positions.extend(userstrategy.position_set.all())

        unique_date = []

        for position in positions:
            if position.date not in unique_date:
                unique_date.append(position.date)

        # optimization
        # unique_date = [position.date for position in positions if position.date not in locals().get('unique_date', []) and locals()['unique_date'].append(position.date)]

        # apply filter fromdate and todate
        if fromdate != None:
            unique_date = [date for date in unique_date if date >= fromdate]
        if todate != None:
            unique_date = [date for date in unique_date if date <= todate]

        # single day position
        same_days_positions = []
        for date in unique_date:
            same_days_position = []
            for position in positions:
                if position.date == date:
                    same_days_position.append(position)

            position = {
                "date": str(date),
                "profit_loss": str(
                    sum(position.profit_loss for position in same_days_position)
                ),
            }
            same_days_positions.append(position)

        return same_days_positions


#####################################################################   LIBRARIES   ########################################################################

from datetime import datetime
import graphene
from graphene_django import DjangoObjectType
from django.db.models import Q
from pytz import timezone


from apis.models import (UserStrategy)
from apis.schema.types.position_type import PositionType

kolkata = timezone("Asia/Kolkata")


def _positions_qs(self, date, userstrategy_ids):
    """Open positions (quantity != 0) are always returned regardless of
    date; closed positions are filtered to the selected date (defaults to
    today IST when not given). userstrategy_ids further narrows the set
    when present.
    """
    qs = self.position_set.all()
    if userstrategy_ids:
        qs = qs.filter(user_strategy__in=userstrategy_ids)
    target_date = date if date else datetime.now(tz=kolkata).date()
    return qs.filter(Q(created_at__date=target_date) | ~Q(quantity=0)).order_by(
        "-created_at"
    )

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
    def resolve_total_position_count(self, info, date="", userstrategy_ids=[]):
        return _positions_qs(self, date, userstrategy_ids).count()

    def resolve_active_positions_count(self, info, date="", userstrategy_ids=[]):
        # Open positions (quantity != 0) regardless of date.
        qs = self.position_set.exclude(quantity=0)
        if userstrategy_ids:
            qs = qs.filter(user_strategy__in=userstrategy_ids)
        return qs.count()

    def resolve_total_profit_loss(self, info, date="", userstrategy_ids=[]):
        # Match the per-position formula in PositionType.resolve_profit_loss
        # so the strategy total agrees with the row-level numbers.
        # The *100 is XAU contract size (1 lot = 100 oz). When the platform
        # adds non-gold instruments, move this multiplier onto CurrencyPair.
        positions = _positions_qs(self, date, userstrategy_ids)
        return sum(
            (
                float(p.realized_profit_loss)
                + (float(p.currencypair.ltp) - float(p.avg_buy_price))
                * float(p.quantity)
            )
            * 100
            for p in positions
        )


    # get specific broker name
    def resolve_brokerName(self, info):
        return self.user_broker.broker.name

    # fetching position values for user

    def resolve_positions(self, info, date="", userstrategy_ids=[]):
        return _positions_qs(self, date, userstrategy_ids)

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

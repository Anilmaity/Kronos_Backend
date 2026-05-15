import graphene

from apis.models import CurrencyPair
from apis.schema.utils import user_authenticate
from apis.schema.types.currency_pair_type import CurrencyPairType



class PeriodType(graphene.ObjectType):
    value = graphene.String()



class AllPeriod(graphene.ObjectType):
    all_period = graphene.List(PeriodType)


    @user_authenticate
    def resolve_all_period(self, info):
        periods  = ["1m","3m","5m","10m","15m","30m","1h","2h","4h","6h","8h","12h","1d","3d","1w","1M"]
        response = []
        for period in periods:
            response.append(PeriodType(value=period))
        return response
import graphene

from apis.models import CurrencyPair
from apis.schema.utils import user_authenticate
from apis.schema.types.currency_pair_type import CurrencyPairType


class AllCurrencyPair(graphene.ObjectType):
    all_currency_pair = graphene.List(CurrencyPairType)


    @user_authenticate
    def resolve_all_currency_pair(self, info):
        return CurrencyPair.objects.all().order_by("-created_at")

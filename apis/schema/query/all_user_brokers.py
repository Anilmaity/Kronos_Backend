import graphene
from graphql import GraphQLError

from apis.models import *
from apis.schema.types.user_broker_type import UserBrokerType
from apis.schema.utils import *


class AllUserBrokers(graphene.ObjectType):
    all_user_brokers = graphene.List(UserBrokerType, include_dummy=graphene.Boolean())



    @admin_authenticate  # logic to authenticate admin
    def resolve_all_user_brokers(self, info, include_dummy=True):
        return (UserBroker.objects.all().order_by("broker__name")
                if include_dummy
                else UserBroker.objects.exclude(broker__name="Dummy")
                )


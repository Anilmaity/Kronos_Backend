import graphene
from graphql import GraphQLError

from apis.models import *
from apis.schema.utils import *


class GetUserPosition(graphene.ObjectType):
    get_user_positions = graphene.JSONString(id=graphene.String())

    @user_authenticate
    def resolve_get_user_positions(self, info, id):
        try:
            if info.context.user.is_superuser:
                userbroker = UserBroker.objects.get(id=id)
            else:
                userbroker = UserBroker.objects.get(user=info.context.user, id=id)
        except UserBroker.DoesNotExist:
            raise GraphQLError("Invalid Id")

        # FIXME why only Finvasia

        res = "Broker not supported"
        return res


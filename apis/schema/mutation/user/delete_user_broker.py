
import graphql_jwt

import graphene

from graphql_jwt.shortcuts import get_token

from apis.models import UserBroker
from apis.schema.utils import admin_authenticate

class DeleteUserBroker(graphene.Mutation):
    Response = graphene.String()

    class Arguments:
        broker_id = graphene.String(required=True)

    @admin_authenticate
    def mutate(self, info, broker_id):
        try:
            userbroker = UserBroker.objects.get(id=broker_id)
            userbroker.delete()
            return DeleteUserBroker(Response="Success")
        except UserBroker.DoesNotExist:
            return DeleteUserBroker(Response="Broker Not Found")
import graphene
from graphql_auth import mutations
from graphql_auth.schema import UserQuery, MeQuery
from graphene_django.debug import DjangoDebug

from apis.schema.query import CustomQuery
from apis.schema.mutation import AdminMutation, BrokerMutation, UserMutation
from apis.models import *


class Query(UserQuery, MeQuery, CustomQuery):
    debug = graphene.Field(DjangoDebug, name="_debug")


class AuthMutation(graphene.ObjectType):
    verify_token = mutations.VerifyToken.Field()
    token_auth = mutations.ObtainJSONWebToken.Field()


class Mutation(AdminMutation, AuthMutation, BrokerMutation, UserMutation):
    pass


schema = graphene.Schema(query=Query, mutation=Mutation)

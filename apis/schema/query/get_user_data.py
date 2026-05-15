import graphene

from apis.models import *
from apis.schema.utils import user_authenticate
from apis.schema.types.user_type import UserType


class GetUserData(graphene.ObjectType):
    getuserdata = graphene.Field(UserType)


    @user_authenticate
    def resolve_getuserdata(self, info):
        user = info.context.user
        return user



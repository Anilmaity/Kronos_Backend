
import graphql_jwt

import graphene

from graphql_jwt.shortcuts import get_token

from apis.models import User
from apis.schema.utils import user_authenticate
from apis.schema.types.user_type import UserType


class UpdateUser(graphene.Mutation):
    User = graphene.Field(UserType)
    Response = graphene.String()

    class Arguments:
        email = graphene.String(required=True)

        mobile_no = graphene.String(required=False)
        state = graphene.String(required=False)
        profile_description = graphene.String(required=False)
        pan_number = graphene.String(required=False)

    @user_authenticate
    def mutate(
        self,
        info,
        email,
        mobile_no=None,
        state=None,
        profile_description=None,
        pan_number=None,
    ):
        try:
            user = User.objects.get(email=email)
            if mobile_no != None:
                user.mobile_no = mobile_no
            if state != None:
                user.state = state
            if profile_description != None:
                user.profile_description = profile_description
            if pan_number != None:
                user.pan_number = pan_number
            user.save()
            return UpdateUser(User=user, Response="Success")

        except User.DoesNotExist:
            return UpdateUser(User=None, Response="User Not Found")

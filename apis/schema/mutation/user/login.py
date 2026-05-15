
import graphene

from graphql_jwt.shortcuts import get_token
from django.contrib.auth import authenticate

from apis.models import User
from apis.schema.types.user_type import UserType


class Login(graphene.Mutation):
    User = graphene.Field(UserType)
    token = graphene.String()
    Response = graphene.String()
    success = graphene.Boolean()

    class Arguments:
        email = graphene.String(required=True)
        password = graphene.String(required=True)

    def mutate(self, info, email, password):
        try:
            authenticated_user = authenticate(username=email, password=password)

            if authenticated_user is not None:
                if authenticated_user.is_active == False:
                    return Login(Response="User Not Activated please verify account in email", success=False)
                token = get_token(authenticated_user)
                return Login(User=authenticated_user, Response="Success", success=True, token=token)
            else:
                return Login(Response="Invalid User or Password", success=False)
        except User.DoesNotExist:
            return Login(Response="User not found", success=False)

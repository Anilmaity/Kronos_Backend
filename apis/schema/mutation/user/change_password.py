
import graphql_jwt

import graphene
from django.contrib.auth.hashers import check_password, make_password
from graphql import GraphQLError

from apis.models import User

CURRENTLY_ACTIVE = "Currently Active"
class ChangePassword(graphene.Mutation):
    Response = graphene.String()

    class Arguments:
        email = graphene.String(required=False)
        password = graphene.String(required=True)
        new_password = graphene.String(required=True)

    def mutate(self, info, password, new_password, email=None):
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return ChangePassword(Response="User Not Found")
        if not check_password(password, user.password):
            raise GraphQLError("Old password is Wrong!")
        hash_pass = make_password(new_password)
        user.password = hash_pass
        user.save()
        return ChangePassword(Response="Success")
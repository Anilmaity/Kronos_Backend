
import graphql_jwt

import graphene

from graphql_jwt.shortcuts import get_token

class VerifyToken(graphene.Mutation):
    success = graphene.Boolean()

    class Arguments:
        token = graphene.String()

    def mutate(self, info, token):
        # Check if the token is valid
        try:
            user = graphql_jwt.shortcuts.get_user_by_token(token)

            if user.is_authenticated:
                return VerifyToken(success=True)
        except Exception:
            return VerifyToken(success=False)
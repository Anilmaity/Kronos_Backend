
import logging

import graphene
import graphql_jwt.shortcuts

logger = logging.getLogger(__name__)


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
            logger.warning("VerifyToken: token validation failed", exc_info=True)
            return VerifyToken(success=False)

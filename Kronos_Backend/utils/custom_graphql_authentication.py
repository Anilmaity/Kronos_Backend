from graphql_auth.backends import GraphQLAuthBackend
from graphql_jwt.exceptions import JSONWebTokenError
from graphql_jwt.shortcuts import get_user_by_token
from graphql_jwt.utils import get_credentials


class CustomGraphQLAuthBackend(GraphQLAuthBackend):
    def authenticate(self, request=None, **kwargs):
        if request is None or getattr(request, "_jwt_token_auth", False):
            return None

        token = get_credentials(request, **kwargs)

        try:
            if token is not None:
                return get_user_by_token(token, request), None
        except JSONWebTokenError:
            pass

        return None

    def authenticate_header(self, request):
        return 'JWT realm="api"'

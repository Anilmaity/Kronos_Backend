

import graphene

from datetime import datetime, timedelta

import jwt

from apis.models import User


class VerifyAccount(graphene.Mutation):
    Response = graphene.String()

    class Arguments:
        token = graphene.String(required=True)

    def mutate(self, info, token):

        try:
            decoded_payload = jwt.decode(token, "algoacharya", algorithms=["HS256"])
            email = decoded_payload["email"]
            current_time = datetime.utcnow()
            if current_time > datetime.utcfromtimestamp(decoded_payload["exp"]):
                return VerifyAccount(Response="TOKEN_EXPIRED")
            try:
                user = User.objects.get(email=email)
                if user.is_active:
                    return VerifyAccount(Response="Account Already Verified")
                else:
                    user.is_active = True
                    user.save()
                    return VerifyAccount(Response="Account Verified")
            except User.DoesNotExist:
                return VerifyAccount(Response="User Not Found")

        except jwt.ExpiredSignatureError:
            return VerifyAccount(Response="TOKEN_EXPIRED")

        except jwt.InvalidTokenError:
            return VerifyAccount(Response="INVALID_TOKEN")

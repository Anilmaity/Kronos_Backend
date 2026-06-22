import graphene

from apis.models import UserBroker
from apis.schema.utils import user_authenticate
from apis.schema.types.user_broker_type import UserBrokerType
from apis.crypto import encrypt_token


class AddAccount(graphene.Mutation):
    Response = graphene.String()
    UserBroker = graphene.Field(UserBrokerType)

    class Arguments:
        label = graphene.String(required=True)
        meta_account_id = graphene.String(required=True)
        meta_api_token = graphene.String(required=True)

    @user_authenticate
    def mutate(self, info, label, meta_account_id, meta_api_token):
        try:
            enc = encrypt_token(meta_api_token)
        except Exception:
            return AddAccount(
                Response="Server encryption key not configured", UserBroker=None
            )
        broker = UserBroker.objects.create(
            user=info.context.user,
            label=label,
            meta_account_id=meta_account_id,
            meta_api_token_enc=enc,
            meta_api_token_last4=meta_api_token[-4:],
        )
        return AddAccount(Response="Success", UserBroker=broker)

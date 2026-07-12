import logging

import graphene

from apis.models import UserBroker
from apis.schema.utils import user_authenticate
from apis.schema.types.user_broker_type import UserBrokerType
from apis.crypto import encrypt_token

logger = logging.getLogger(__name__)


class UpdateAccount(graphene.Mutation):
    Response = graphene.String()
    UserBroker = graphene.Field(UserBrokerType)

    class Arguments:
        id = graphene.String(required=True)
        label = graphene.String()
        meta_account_id = graphene.String()
        meta_api_token = graphene.String()

    @user_authenticate
    def mutate(self, info, id, label=None, meta_account_id=None, meta_api_token=None):
        try:
            if info.context.user.is_superuser:
                broker = UserBroker.objects.get(id=id)
            else:
                broker = UserBroker.objects.get(id=id, user=info.context.user)
        except UserBroker.DoesNotExist:
            return UpdateAccount(Response="Account does not exist", UserBroker=None)

        if label is not None:
            broker.label = label
        if meta_account_id is not None:
            broker.meta_account_id = meta_account_id
        if meta_api_token:
            try:
                broker.meta_api_token_enc = encrypt_token(meta_api_token)
            except Exception:
                logger.exception("UpdateAccount: token encryption failed")
                return UpdateAccount(
                    Response="Server encryption key not configured", UserBroker=None
                )
            broker.meta_api_token_last4 = meta_api_token[-4:]

        broker.save()
        return UpdateAccount(Response="Success", UserBroker=broker)

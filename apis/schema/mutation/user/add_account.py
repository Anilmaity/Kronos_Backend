import logging
import uuid

import graphene

from apis.models import UserBroker
from apis.schema.utils import user_authenticate
from apis.schema.types.user_broker_type import UserBrokerType
from apis.crypto import encrypt_token

logger = logging.getLogger(__name__)


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
            logger.exception("AddAccount: token encryption failed")
            return AddAccount(
                Response="Server encryption key not configured", UserBroker=None
            )
        broker = UserBroker.objects.create(
            user=info.context.user,
            # Explicit unique api_key: the model's default is a broken static
            # string (str(uuid.uuid4) evaluated at class-load), so every create
            # without an explicit value would collide on the unique constraint.
            api_key=str(uuid.uuid4()),
            label=label,
            meta_account_id=meta_account_id,
            meta_api_token_enc=enc,
            meta_api_token_last4=meta_api_token[-4:],
        )
        return AddAccount(Response="Success", UserBroker=broker)

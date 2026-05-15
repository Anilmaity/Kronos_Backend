
import graphene

from apis.models import UserBroker
from apis.schema.utils import user_authenticate
from apis.schema.types.user_broker_type import UserBrokerType


class ToggleTrailingStoploss(graphene.Mutation):
    Response = graphene.String()
    UserBroker = graphene.Field(UserBrokerType)

    class Arguments:
        userbroker_id = graphene.String(required=True)

    @user_authenticate
    def mutate(self, info, userbroker_id):
        try:
            if info.context.user.is_superuser:
                userbroker = UserBroker.objects.get(id=userbroker_id)
            else:
                userbroker = UserBroker.objects.get(
                    user=info.context.user, id=userbroker_id
                )
            userbroker.activate_trailing_stoploss = not userbroker.activate_trailing_stoploss
            userbroker.save()
            return ToggleTrailingStoploss(Response="Success", UserBroker=userbroker)
        except UserBroker.DoesNotExist:
            return ToggleTrailingStoploss(Response="Not Exist UserBroker", UserBroker=None)

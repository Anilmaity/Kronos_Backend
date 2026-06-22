import graphene

from apis.models import UserBroker
from apis.schema.utils import user_authenticate


class DeleteUserBroker(graphene.Mutation):
    Response = graphene.String()

    class Arguments:
        broker_id = graphene.String(required=True)

    @user_authenticate
    def mutate(self, info, broker_id):
        try:
            if info.context.user.is_superuser:
                userbroker = UserBroker.objects.get(id=broker_id)
            else:
                userbroker = UserBroker.objects.get(
                    id=broker_id, user=info.context.user
                )
            userbroker.delete()
            return DeleteUserBroker(Response="Success")
        except UserBroker.DoesNotExist:
            return DeleteUserBroker(Response="Broker Not Found")


import graphene

from apis.models import UserStrategy
from apis.schema.utils import user_authenticate


class DeleteUserStrategy(graphene.Mutation):
    Response = graphene.String()

    class Arguments:
        id = graphene.String(required=True)

    @user_authenticate
    def mutate(self, info, id):
        if info.context.user.is_superuser:
            UserStrategy.objects.filter(id=id).delete()
        else:
            UserStrategy.objects.filter(user_broker__user=info.context.user, id=id).delete()
        return DeleteUserStrategy(Response="Strategy Deleted Successfully")
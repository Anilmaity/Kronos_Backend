
import requests
import graphene
from django.db.models import Q

from apis.models import UserStrategy
from apis.schema.utils import user_authenticate
from apis.schema.types.user_strategy_type import UserStrategyType


EXIT_LAMBDA_URL = "https://yo7uvfbmgdlzlux4vklm7gkdfm0akpav.lambda-url.ap-south-1.on.aws/"


class ExitStrategy(graphene.Mutation):
    Response = graphene.String()
    UserStrategy = graphene.Field(UserStrategyType)

    class Arguments:
        strategy_id = graphene.String(required=True)
        broker_cred_id = graphene.String(required=True)

    @user_authenticate
    def mutate(self, info, strategy_id, broker_cred_id):
        try:
            if info.context.user.is_superuser:
                userstrategy = UserStrategy.objects.get(id=strategy_id)
            else:
                userstrategy = UserStrategy.objects.get(
                    user_broker__user=info.context.user, id=strategy_id
                )
        except UserStrategy.DoesNotExist:
            return ExitStrategy(
                Response="Strategy or UserBroker Does Not Exist", UserStrategy=None
            )

        positions = userstrategy.position_set.filter(~Q(quantity=0))
        if not positions.exists():
            return ExitStrategy(
                Response="No Position to exit", UserStrategy=userstrategy
            )

        exited, failed = 0, 0
        for position in positions:
            payload = {
                "position_id": str(position.id),
                "condition": "Platform Exit",
            }
            try:
                response = requests.post(EXIT_LAMBDA_URL, json=payload, timeout=3)
                response.raise_for_status()
                exited += 1
            except requests.exceptions.Timeout:
                exited += 1
            except requests.exceptions.RequestException:
                failed += 1

        msg = f"Exit requested for {exited} position(s)"
        if failed:
            msg += f", {failed} failed"
        return ExitStrategy(Response=msg, UserStrategy=userstrategy)

import requests
import graphene
from django.db.models import Q

from apis.models import UserStrategy
from apis.schema.utils import user_authenticate
from apis.schema.types.user_strategy_type import UserStrategyType


EXIT_LAMBDA_URL = "https://yo7uvfbmgdlzlux4vklm7gkdfm0akpav.lambda-url.ap-south-1.on.aws/"


def request_position_exits(positions, post=requests.post):
    """POST one exit request per position to the exit Lambda.

    Returns (confirmed, pending, failed):
      confirmed - Lambda returned 2xx
      pending   - request timed out; outcome unknown, do NOT claim success
      failed    - connection error or non-2xx response
    """
    confirmed = pending = failed = 0
    for position in positions:
        payload = {"position_id": str(position.id), "condition": "Platform Exit"}
        try:
            response = post(EXIT_LAMBDA_URL, json=payload, timeout=3)
            response.raise_for_status()
            confirmed += 1
        except requests.exceptions.Timeout:
            pending += 1
        except requests.exceptions.RequestException:
            failed += 1
    return confirmed, pending, failed


def build_exit_message(confirmed, pending, failed):
    parts = [f"{confirmed} exited"]
    if pending:
        parts.append(f"{pending} pending confirmation")
    if failed:
        parts.append(f"{failed} failed")
    return "Exit requested: " + ", ".join(parts)


class ExitStrategy(graphene.Mutation):
    Response = graphene.String()
    Ok = graphene.Boolean()
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
                Response="Strategy or UserBroker Does Not Exist",
                Ok=False,
                UserStrategy=None,
            )

        positions = userstrategy.position_set.filter(~Q(quantity=0))
        if not positions.exists():
            return ExitStrategy(
                Response="No Position to exit", Ok=True, UserStrategy=userstrategy
            )

        confirmed, pending, failed = request_position_exits(positions)
        return ExitStrategy(
            Response=build_exit_message(confirmed, pending, failed),
            Ok=(failed == 0),
            UserStrategy=userstrategy,
        )

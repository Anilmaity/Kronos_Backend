
import graphql_jwt
import requests
import graphene
from django.db.models import Q

from graphql_jwt.shortcuts import get_token

from apis.models import UserStrategy
from apis.schema.utils import user_authenticate
from apis.schema.types.user_strategy_type import UserStrategyType


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
                userstrategy = UserStrategy.objects.get(user_broker__user=info.context.user, id=strategy_id)

            positions = userstrategy.position_set.filter(~Q(quantity=0))
            if len(positions) != 0:
                for position in positions:
                    print(position.id)
                    payload = {
                        "position_id": str(position.id),
                        "condition": "Platform Exit"
                    }
                    function_url = "https://yo7uvfbmgdlzlux4vklm7gkdfm0akpav.lambda-url.ap-south-1.on.aws/"
                    try:
                        # Use POST instead of GET for sending JSON payload
                        response = requests.post(function_url, json=payload, timeout=3)
                        response.raise_for_status()  # Raise an error for bad responses (4xx, 5xx)
                        # print(response.text, response.status_code)
                        return ExitStrategy(Response=response.text, UserStrategy=userstrategy)
                    except requests.exceptions.Timeout:
                        return ExitStrategy(Response="Position Exited Successfully", UserStrategy=userstrategy)

                    except requests.exceptions.RequestException as e:
                        return ExitStrategy(Response="Unexpected Error from Backtest ",  UserStrategy=userstrategy)
            else:
                return ExitStrategy(Response="No Position to exit", UserStrategy=userstrategy)
        except UserStrategy.DoesNotExist:
            return ExitStrategy(Response="Strategy or UserBroker Does Not Exist", UserStrategy=None)

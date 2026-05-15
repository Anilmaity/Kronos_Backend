
from datetime import datetime, timedelta

import graphene
import pytz
import requests


from apis.schema.utils import admin_authenticate, user_authenticate

# Timezone


kolkata = pytz.timezone("Asia/Kolkata")

class GenerateBackTestReport(graphene.Mutation):
    Response = graphene.String()
    Success = graphene.Boolean()

    class Arguments:
        strategy_id = graphene.String(required=True)
        from_date = graphene.Date(required=True)
        to_date = graphene.Date(required=True)

    @user_authenticate
    def mutate(self, info, strategy_id, from_date, to_date):
        user = info.context.user
        user_email = user.email

        if from_date > to_date:
            return GenerateBackTestReport(
                Response="From date should be less than to date", Success=False
            )
        if from_date > datetime.now(tz=kolkata).date():
            return GenerateBackTestReport(
                Response="From date should be less than current date", Success=False
            )
        if to_date > datetime.now(tz=kolkata).date():
            return GenerateBackTestReport(
                Response="To date should be less than current date", Success=False
            )
        if from_date < datetime.now(tz=kolkata).date() - timedelta(days=365):
            return GenerateBackTestReport(
                Response="From date should be within 12 month", Success=False
            )

        payload = {
            "user_email": user_email,
            "strategy_id": strategy_id,
            "from_date": str(from_date),
            "to_date": str(to_date),
        }
        function_url = "https://3gph2bxeezeozfb2lbqwelavoa0lvjct.lambda-url.ap-south-1.on.aws/"
        try:
            # Use POST instead of GET for sending JSON payload
            response = requests.post(function_url, json=payload, timeout=3)
            response.raise_for_status()  # Raise an error for bad responses (4xx, 5xx)
            # print(response.text, response.status_code)
            return GenerateBackTestReport(
                Response=response.text, Success=False
            )
        except requests.exceptions.Timeout:
            return GenerateBackTestReport(
                Response="Backtest Report is being generated", Success=True
            )
        except requests.exceptions.RequestException as e:
            return GenerateBackTestReport(
                Response="Unexpected Error from Backtest ", Success=True
            )



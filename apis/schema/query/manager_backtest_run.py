import graphene

from apis.models import ManagerBacktestRun as ManagerBacktestRunModel
from apis.schema.query.manager_backtest_runs import ManagerBacktestRunDetailType
from apis.schema.utils import user_authenticate


class ManagerBacktestRun(graphene.ObjectType):
    managerBacktestRun = graphene.Field(
        ManagerBacktestRunDetailType, runId=graphene.UUID(required=True)
    )

    @user_authenticate
    def resolve_managerBacktestRun(self, info, runId):
        return ManagerBacktestRunModel.objects.filter(id=runId).first()

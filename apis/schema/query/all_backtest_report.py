import graphene

from apis.models import BacktestReport
from apis.schema.utils import user_authenticate
from apis.schema.types.backtest_report_type import BacktestReportType


class AllBacktestReport(graphene.ObjectType):
    allBacktestReport = graphene.List(
        BacktestReportType,
        strategyId=graphene.String(required=False),
        runLabel=graphene.String(required=False),
    )

    @user_authenticate
    def resolve_allBacktestReport(self, info, strategyId=None, runLabel=None):
        qs = BacktestReport.objects.select_related("strategy").all()
        if strategyId:
            qs = qs.filter(strategy_id=strategyId)
        if runLabel:
            qs = qs.filter(run_label=runLabel)
        return qs.order_by("-created_at")

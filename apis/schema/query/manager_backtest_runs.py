import graphene
from graphene.types.generic import GenericScalar

from apis.models import ManagerBacktestRun as ManagerBacktestRunModel
from apis.schema.utils import user_authenticate


class ManagerBacktestRunSummaryType(graphene.ObjectType):
    id = graphene.UUID()
    label = graphene.String()
    status = graphene.String()
    progressPct = graphene.Float()
    phase = graphene.String()
    periodStart = graphene.Date()
    periodEnd = graphene.Date()
    createdAt = graphene.DateTime()

    def resolve_progressPct(self, info):
        return self.progress_pct

    def resolve_periodStart(self, info):
        return self.period_start

    def resolve_periodEnd(self, info):
        return self.period_end

    def resolve_createdAt(self, info):
        return self.created_at


class ManagerBacktestRunDetailType(ManagerBacktestRunSummaryType):
    params = GenericScalar()
    result = GenericScalar()
    error = graphene.String()
    startedAt = graphene.DateTime()
    finishedAt = graphene.DateTime()

    def resolve_startedAt(self, info):
        return self.started_at

    def resolve_finishedAt(self, info):
        return self.finished_at


class ManagerBacktestRuns(graphene.ObjectType):
    managerBacktestRuns = graphene.List(ManagerBacktestRunSummaryType)

    @user_authenticate
    def resolve_managerBacktestRuns(self, info):
        return ManagerBacktestRunModel.objects.order_by("-created_at")[:100]

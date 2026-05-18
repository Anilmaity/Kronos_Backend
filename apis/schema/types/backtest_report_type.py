import graphene
from graphene_django import DjangoObjectType

from apis.models import BacktestReport


class BacktestReportType(DjangoObjectType):
    strategy_name = graphene.String()
    strategy_id = graphene.String()

    class Meta:
        model = BacktestReport
        fields = (
            "id",
            "created_at",
            "modified_at",
            "run_label",
            "period_start",
            "period_end",
            "trades",
            "wins",
            "losses",
            "win_rate_pct",
            "pnl_pts",
            "max_dd_pts",
            "avg_win_pts",
            "avg_loss_pts",
            "profit_factor",
            "expectancy_pts",
            "sharpe_daily",
            "source_csv",
            "params_snapshot",
            "notes",
        )

    def resolve_strategy_name(self, info):
        return self.strategy.name if self.strategy_id else None

    def resolve_strategy_id(self, info):
        return str(self.strategy_id) if self.strategy_id else None

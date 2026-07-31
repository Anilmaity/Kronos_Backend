from datetime import date

import graphene

from apis.models import ManagedStrategy, ManagerBacktestRun
from apis.schema.query.strategy_manager_state import get_or_create_manager_config
from apis.schema.utils import user_authenticate

MAX_WINDOW_DAYS = 366
MAX_QUEUED = 3

# Fallbacks for knobs ManagerConfig does not carry (engine SimConfig defaults).
DEFAULT_SPREAD_PTS = 0.30
DEFAULT_SLIPPAGE_PTS = 0.10
DEFAULT_LOTS = 0.02
DEFAULT_REGIME_CADENCE_MIN = 5


def _roster_snapshot():
    """Capture the armed roster (PAPER/LIVE) at submit time. The worker replays
    exactly this list; the frontend never supplies it."""
    qs = (
        ManagedStrategy.objects.select_related("user_strategy__strategy")
        .filter(arm_mode__in=["PAPER", "LIVE"])
        .order_by("slot", "created_at")
    )
    return [
        {
            "name": ms.user_strategy.strategy.name,
            "policy_key": ms.policy_key,
            "policy_params": ms.policy_params or {},
        }
        for ms in qs
    ]


class RunManagerBacktest(graphene.Mutation):
    """Queue a Strategy Manager historical-audit backtest. The strategies-stack
    backtest_worker picks up PENDING rows FIFO; poll managerBacktestRuns."""

    ok = graphene.Boolean()
    run_id = graphene.UUID()
    error = graphene.String()

    class Arguments:
        period_start = graphene.Date(required=True)
        period_end = graphene.Date(required=True)
        label = graphene.String()
        spread_pts = graphene.Float()
        slippage_pts = graphene.Float()
        lots = graphene.Float()
        kill_switch_usd = graphene.Float()
        max_concurrent = graphene.Int()
        regime_cadence_min = graphene.Int()
        include_ungated = graphene.Boolean()

    @user_authenticate
    def mutate(self, info, period_start, period_end, label=None, spread_pts=None,
               slippage_pts=None, lots=None, kill_switch_usd=None,
               max_concurrent=None, regime_cadence_min=None, include_ungated=None):
        if period_start >= period_end:
            return RunManagerBacktest(ok=False, run_id=None,
                                      error="period_start must be before period_end")
        if period_end > date.today():
            return RunManagerBacktest(ok=False, run_id=None,
                                      error="period_end cannot be in the future")
        if (period_end - period_start).days > MAX_WINDOW_DAYS:
            return RunManagerBacktest(
                ok=False, run_id=None,
                error=f"window exceeds {MAX_WINDOW_DAYS} days")

        queued = ManagerBacktestRun.objects.filter(
            status__in=["PENDING", "RUNNING"]).count()
        if queued >= MAX_QUEUED:
            return RunManagerBacktest(
                ok=False, run_id=None,
                error=f"queue full: {queued} runs already pending/running")

        config = get_or_create_manager_config()
        params = {
            "spread_pts": spread_pts if spread_pts is not None else DEFAULT_SPREAD_PTS,
            "slippage_pts": (slippage_pts if slippage_pts is not None
                             else DEFAULT_SLIPPAGE_PTS),
            "lots": lots if lots is not None else DEFAULT_LOTS,
            "kill_switch_usd": (kill_switch_usd if kill_switch_usd is not None
                                else float(config.kill_switch_loss_usd)),
            "max_concurrent": (max_concurrent if max_concurrent is not None
                               else config.max_concurrent_positions),
            "regime_cadence_min": (regime_cadence_min if regime_cadence_min is not None
                                   else DEFAULT_REGIME_CADENCE_MIN),
            "include_ungated": bool(include_ungated),
            "roster_snapshot": _roster_snapshot(),
        }

        run = ManagerBacktestRun.objects.create(
            label=label or f"audit_{period_start}_{period_end}",
            period_start=period_start,
            period_end=period_end,
            params=params,
            requested_by=info.context.user,
        )
        return RunManagerBacktest(ok=True, run_id=run.id, error=None)

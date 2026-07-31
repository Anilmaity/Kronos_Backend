import graphene
from django.utils import timezone

from apis.models import ManagerBacktestRun
from apis.schema.utils import user_authenticate


class CancelManagerBacktest(graphene.Mutation):
    """Cancel a queued or running manager backtest. The worker honors the flag
    between progress chunks; a PENDING row is simply never picked up."""

    ok = graphene.Boolean()
    error = graphene.String()

    class Arguments:
        run_id = graphene.UUID(required=True)

    @user_authenticate
    def mutate(self, info, run_id):
        # queryset .update() skips auto_now — stamp modified_at explicitly, and
        # give PENDING rows (which the worker will never touch) a finished_at.
        updated = ManagerBacktestRun.objects.filter(
            id=run_id, status__in=["PENDING", "RUNNING"]
        ).update(status="CANCELLED", modified_at=timezone.now(),
                 finished_at=timezone.now())
        if not updated:
            return CancelManagerBacktest(
                ok=False, error="run not found or already terminal")
        return CancelManagerBacktest(ok=True, error=None)

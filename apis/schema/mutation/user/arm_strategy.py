import graphene

from apis.models import ManagedStrategy
from apis.schema.utils import user_authenticate
from apis.schema.types.managed_strategy_type import ManagedStrategyType

VALID_ARM_MODES = ("OFF", "PAPER", "LIVE")


class ArmStrategy(graphene.Mutation):
    """Set a managed strategy's arm mode (OFF / PAPER / LIVE).

    LIVE is refused unless the strategy is live_eligible (set only from
    held-out backtest verdicts) — the user cannot arm an unvalidated edge.
    """

    Response = graphene.String()
    ManagedStrategy = graphene.Field(ManagedStrategyType)

    class Arguments:
        managed_strategy_id = graphene.String(required=True)
        arm_mode = graphene.String(required=True)

    @user_authenticate
    def mutate(self, info, managed_strategy_id, arm_mode):
        arm_mode = arm_mode.upper()
        if arm_mode not in VALID_ARM_MODES:
            return ArmStrategy(
                Response="Invalid arm mode: must be OFF, PAPER or LIVE",
                ManagedStrategy=None,
            )

        try:
            if info.context.user.is_superuser:
                ms = ManagedStrategy.objects.get(id=managed_strategy_id)
            else:
                ms = ManagedStrategy.objects.get(
                    id=managed_strategy_id,
                    user_strategy__user_broker__user=info.context.user,
                )
        except ManagedStrategy.DoesNotExist:
            return ArmStrategy(
                Response="Managed Strategy Does Not Exist", ManagedStrategy=None
            )

        if arm_mode == "LIVE" and not ms.live_eligible:
            return ArmStrategy(
                Response=(
                    "Cannot arm LIVE: strategy is not live-eligible "
                    "(no positive held-out backtest verdict). PAPER is the ceiling."
                ),
                ManagedStrategy=ms,
            )

        ms.arm_mode = arm_mode
        ms.save()
        return ArmStrategy(Response="Success", ManagedStrategy=ms)

import graphene

from apis.models import ManagedStrategy, ManagerAction, ManagerConfig, RegimeSnapshot
from apis.schema.utils import user_authenticate
from apis.schema.types.managed_strategy_type import ManagedStrategyType
from apis.schema.types.manager_action_type import ManagerActionType
from apis.schema.types.manager_config_type import ManagerConfigType
from apis.schema.types.regime_snapshot_type import RegimeSnapshotType

DEFAULT_ACTION_LIMIT = 50


def get_or_create_manager_config():
    """The ManagerConfig is a singleton row; create the safe default (master
    OFF — the manager computes/records but flips nothing) if absent."""
    config = ManagerConfig.objects.order_by("created_at").first()
    if config is None:
        config = ManagerConfig.objects.create()
    return config


class StrategyManagerState(graphene.ObjectType):
    manager_config = graphene.Field(ManagerConfigType)
    managed_strategies = graphene.List(ManagedStrategyType)
    latest_regime = graphene.Field(RegimeSnapshotType, symbol=graphene.String())
    manager_actions = graphene.List(ManagerActionType, limit=graphene.Int())

    @user_authenticate
    def resolve_manager_config(self, info):
        return get_or_create_manager_config()

    @user_authenticate
    def resolve_managed_strategies(self, info):
        qs = ManagedStrategy.objects.all()
        if not info.context.user.is_superuser:
            qs = qs.filter(user_strategy__user_broker__user=info.context.user)
        return qs.order_by("slot", "created_at")

    @user_authenticate
    def resolve_latest_regime(self, info, symbol="XAU_USD"):
        return (
            RegimeSnapshot.objects.filter(symbol=symbol)
            .order_by("-created_at")
            .first()
        )

    @user_authenticate
    def resolve_manager_actions(self, info, limit=DEFAULT_ACTION_LIMIT):
        limit = max(1, min(limit, 500))
        return ManagerAction.objects.order_by("-created_at")[:limit]

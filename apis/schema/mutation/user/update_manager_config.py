from decimal import Decimal

import graphene

from apis.schema.utils import user_authenticate
from apis.schema.types.manager_config_type import ManagerConfigType
from apis.schema.query.strategy_manager_state import get_or_create_manager_config


class UpdateManagerConfig(graphene.Mutation):
    """Update the global manager guards: daily kill-switch loss (USD) and the
    max concurrent open positions across managed children."""

    Response = graphene.String()
    ManagerConfig = graphene.Field(ManagerConfigType)

    class Arguments:
        kill_switch_loss_usd = graphene.Float()
        max_concurrent_positions = graphene.Int()

    @user_authenticate
    def mutate(self, info, kill_switch_loss_usd=None, max_concurrent_positions=None):
        if kill_switch_loss_usd is None and max_concurrent_positions is None:
            return UpdateManagerConfig(
                Response="Nothing to update", ManagerConfig=None
            )

        if kill_switch_loss_usd is not None and kill_switch_loss_usd <= 0:
            return UpdateManagerConfig(
                Response="killSwitchLossUsd must be a positive dollar amount",
                ManagerConfig=None,
            )
        if max_concurrent_positions is not None and max_concurrent_positions < 1:
            return UpdateManagerConfig(
                Response="maxConcurrentPositions must be at least 1",
                ManagerConfig=None,
            )

        config = get_or_create_manager_config()
        if kill_switch_loss_usd is not None:
            config.kill_switch_loss_usd = Decimal(str(round(kill_switch_loss_usd, 2)))
        if max_concurrent_positions is not None:
            config.max_concurrent_positions = max_concurrent_positions
        config.save()
        return UpdateManagerConfig(Response="Success", ManagerConfig=config)

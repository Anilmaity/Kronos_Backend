import graphene

from apis.schema.utils import user_authenticate
from apis.schema.types.manager_config_type import ManagerConfigType
from apis.schema.query.strategy_manager_state import get_or_create_manager_config

VALID_MODES = ("ON", "OFF")


class SetManagerMode(graphene.Mutation):
    """Flip the Strategy Manager master switch. OFF (the default) means the
    manager loop still computes and records regime but flips nothing."""

    Response = graphene.String()
    ManagerConfig = graphene.Field(ManagerConfigType)

    class Arguments:
        master_mode = graphene.String(required=True)

    @user_authenticate
    def mutate(self, info, master_mode):
        master_mode = master_mode.upper()
        if master_mode not in VALID_MODES:
            return SetManagerMode(
                Response="Invalid mode: must be ON or OFF", ManagerConfig=None
            )
        config = get_or_create_manager_config()
        config.master_mode = master_mode
        config.save()
        return SetManagerMode(Response="Success", ManagerConfig=config)

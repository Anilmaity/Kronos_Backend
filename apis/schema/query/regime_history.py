from datetime import timedelta

import graphene
from django.utils import timezone

from apis.models import RegimeSnapshot
from apis.schema.utils import user_authenticate
from apis.schema.types.regime_snapshot_type import RegimeSnapshotType


class RegimeHistory(graphene.ObjectType):
    regime_history = graphene.List(
        RegimeSnapshotType,
        symbol=graphene.String(),
        hours=graphene.Int(),
    )

    @user_authenticate
    def resolve_regime_history(self, info, symbol="XAU_USD", hours=24):
        hours = max(1, min(hours, 24 * 30))  # cap at 30 days
        since = timezone.now() - timedelta(hours=hours)
        return RegimeSnapshot.objects.filter(
            symbol=symbol, created_at__gte=since
        ).order_by("created_at")

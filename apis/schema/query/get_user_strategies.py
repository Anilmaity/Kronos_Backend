import graphene
from graphql import GraphQLError

from apis.models import *
from apis.schema.types.user_strategy_type import UserStrategyType


class GetUserPosition(graphene.ObjectType):
    get_user_strategies = graphene.List(
        UserStrategyType,
        offset=graphene.Int(),
        limit=graphene.Int(),
        brokers=graphene.List(graphene.UUID),
    )

    def resolve_get_user_strategies(self, info, offset=None, limit=None, brokers=None):
        user = info.context.user
        if brokers == None:
            brokers = UserBroker.objects.filter(user=user).order_by("-created_at")

        if offset and limit:
            userstrategies = UserStrategy.objects.filter(
                user_broker__user=user, user_broker__in=brokers
            ).order_by("-name")[offset:limit]
        elif offset:
            userstrategies = UserStrategy.objects.filter(
                user_broker__user=user, user_broker__in=brokers
            ).order_by("-name")[offset:]
        elif limit:
            userstrategies = UserStrategy.objects.filter(
                user_broker__user=user, user_broker__in=brokers
            ).order_by("-name")[:limit]
        else:
            userstrategies = UserStrategy.objects.filter(
                user_broker__user=user, user_broker__in=brokers
            ).order_by("-name")

        return userstrategies


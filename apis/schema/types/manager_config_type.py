from graphene_django import DjangoObjectType

from apis.models import ManagerConfig


class ManagerConfigType(DjangoObjectType):
    class Meta:
        model = ManagerConfig
        fields = "__all__"

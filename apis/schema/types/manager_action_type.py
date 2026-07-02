from graphene_django import DjangoObjectType

from apis.models import ManagerAction


class ManagerActionType(DjangoObjectType):
    class Meta:
        model = ManagerAction
        fields = "__all__"

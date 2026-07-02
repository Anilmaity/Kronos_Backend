from graphene_django import DjangoObjectType

from apis.models import RegimeSnapshot


class RegimeSnapshotType(DjangoObjectType):
    class Meta:
        model = RegimeSnapshot
        fields = "__all__"

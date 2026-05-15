#####################################################################   LIBRARIES   ########################################################################

from graphene_django import DjangoObjectType

from apis.models import (Order)

##############################################################################################################################################################
class OrderType(DjangoObjectType):
    class Meta:
        model = Order
        exclude = ("position",)


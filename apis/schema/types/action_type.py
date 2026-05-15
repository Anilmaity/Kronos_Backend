#####################################################################   LIBRARIES   ########################################################################

from graphene_django import DjangoObjectType

from apis.models import (Action)

##############################################################################################################################################################

class ActionType(DjangoObjectType):
    class Meta:
        model = Action
        exclude = ("strategy",)

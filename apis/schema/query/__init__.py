import graphene

from apis.schema.discovery import discover_classes

imported_classes = list(discover_classes(__package__, __file__).values())


class CustomQuery(*imported_classes, graphene.ObjectType):
    pass

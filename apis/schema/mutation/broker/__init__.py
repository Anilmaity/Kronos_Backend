import graphene

from apis.schema.discovery import discover_classes

imported_classes = discover_classes(__package__, __file__)


class BrokerMutation(graphene.ObjectType):
    pass


for class_name, imported_class in imported_classes.items():
    if hasattr(imported_class, 'Field'):
        setattr(BrokerMutation, class_name, imported_class.Field())

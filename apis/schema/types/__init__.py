from apis.schema.discovery import discover_classes

# Importing the sibling modules is the point here — it registers every
# DjangoObjectType with graphene-django. The collected classes are unused.
imported_classes = discover_classes(__package__, __file__)

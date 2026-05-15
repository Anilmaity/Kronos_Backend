import graphene


class CandleType(graphene.ObjectType):
    time = graphene.DateTime()
    open = graphene.Float()
    high = graphene.Float()
    low = graphene.Float()
    close = graphene.Float()
    volume = graphene.Float()

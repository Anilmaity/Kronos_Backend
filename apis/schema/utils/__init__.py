from graphene_django import DjangoObjectType


def generate_graphene_type(model_input, parms="__all__"):

    class_name = f"{model_input.__name__}Schema"  # Create a dynamic class name
    base_classes = (DjangoObjectType,)

    # Define class attributes
    class_attributes = {
        "Meta": type("Meta", (), {"model": model_input, "fields": parms}),
    }

    # Create the dynamic class using type()
    generated_type = type(class_name, base_classes, class_attributes)

    return generated_type

from functools import wraps

from graphql import GraphQLError


def user_authenticate(func):
    @wraps(func)
    def wrapper(self, info, *args, **kwargs):
        user = info.context.user
        if not user.is_authenticated:
            raise GraphQLError("Authentication Failure : You must be signed in")
        return func(self, info, *args, **kwargs)

    return wrapper


def admin_authenticate(func):
    @wraps(func)
    def wrapper(self, info, *args, **kwargs):
        user = info.context.user
        if not user.is_superuser:
            raise GraphQLError(
                "Authentication Failure : You must be signed with admin account"
            )
        return func(self, info, *args, **kwargs)

    return wrapper



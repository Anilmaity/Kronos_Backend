import os
import importlib
import graphene

base_dir = os.path.dirname(os.path.abspath(__file__))

imported_classes = []

for file_name in os.listdir(base_dir):
    if file_name.endswith('.py') and file_name != '__init__.py':
        module_name = file_name[:-3]
        module_path = f'{__package__}.{module_name}'
        module = importlib.import_module(module_path)
        class_name = ''.join(word.capitalize() for word in module_name.split('_'))
        if hasattr(module, class_name):
            imported_classes.append(getattr(module, class_name))


class CustomQuery(*imported_classes, graphene.ObjectType):
    pass

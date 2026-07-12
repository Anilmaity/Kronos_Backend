"""Shared importlib auto-discovery for the GraphQL schema packages.

Each schema package (query/, mutation/{admin,user,broker}/, types/) previously
carried an identical copy-pasted loop that imports every sibling ``.py`` module
and collects the class whose name is the CamelCase of the module's file name.
This helper is that loop, extracted once, with identical semantics.
"""
import importlib
import logging
import os

logger = logging.getLogger(__name__)


def discover_classes(package, package_file):
    """Import every non-``__init__`` sibling module of ``package_file`` and
    collect ``{class_name: class}`` for the class named after each module
    (CamelCase of the snake_case file name).

    The returned dict preserves ``os.listdir()`` order (insertion order), the
    same order the previous per-package loops produced. Modules that do not
    define the expected class are skipped exactly as before — but now with a
    warning instead of being silently dropped. The warning never raises.
    """
    base_dir = os.path.dirname(os.path.abspath(package_file))
    imported_classes = {}
    for file_name in os.listdir(base_dir):
        if file_name.endswith(".py") and file_name != "__init__.py":
            module_name = file_name[:-3]
            module = importlib.import_module(f"{package}.{module_name}")
            class_name = "".join(word.capitalize() for word in module_name.split("_"))
            if hasattr(module, class_name):
                imported_classes[class_name] = getattr(module, class_name)
            else:
                logger.warning(
                    "Schema discovery: module %s.%s does not define the expected "
                    "class %r; it was skipped.",
                    package,
                    module_name,
                    class_name,
                )
    return imported_classes

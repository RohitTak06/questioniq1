"""Every module imports, and every public function has a docstring and type hints."""

import importlib
import inspect

import pytest

MODULES = [
    "questioniq.config",
    "questioniq.scrape",
    "questioniq.extract",
    "questioniq.segment",
    "questioniq.preprocess",
    "questioniq.topics",
    "questioniq.features",
    "questioniq.difficulty",
    "questioniq.explain",
    "questioniq.trends",
    "questioniq.db",
    "questioniq.pipeline",
    "app",
    "app.routes",
    "scripts.discover_api",
]


def public_functions(module) -> list:
    """Return the public functions defined in a module, not the ones it imports."""
    return [
        func
        for name, func in inspect.getmembers(module, inspect.isfunction)
        if func.__module__ == module.__name__ and not name.startswith("_")
    ]


@pytest.mark.parametrize("name", MODULES)
def test_module_imports_and_has_docstring(name: str) -> None:
    assert importlib.import_module(name).__doc__


@pytest.mark.parametrize("name", MODULES)
def test_public_functions_are_documented_and_typed(name: str) -> None:
    for func in public_functions(importlib.import_module(name)):
        signature = inspect.signature(func)
        assert func.__doc__, f"{func.__name__} has no docstring"
        assert signature.return_annotation is not inspect.Signature.empty, func.__name__
        for param in signature.parameters.values():
            assert param.annotation is not inspect.Parameter.empty, (
                f"{func.__name__}({param.name}) has no type hint"
            )

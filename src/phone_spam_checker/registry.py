"""Registry utilities for phone checkers."""

from typing import Dict, Iterable, Type

import importlib

from .domain.phone_checker import PhoneChecker

CHECKER_REGISTRY: Dict[str, Type[PhoneChecker]] = {}


def register_checker(name: str, cls: Type[PhoneChecker]) -> None:
    """Register a checker class under a given name."""
    CHECKER_REGISTRY[name] = cls


def get_checker_class(name: str) -> Type[PhoneChecker]:
    """Retrieve a checker class by name."""
    return CHECKER_REGISTRY[name]


def list_checkers() -> Iterable[str]:
    """Return names of all registered checkers."""
    return CHECKER_REGISTRY.keys()


def load_checker_module(module_path: str) -> None:
    """Import a module to register additional checkers."""
    importlib.import_module(module_path)


def register_default_checkers() -> None:
    """Register built-in checkers."""
    from .infrastructure import (
        KasperskyWhoCallsChecker,
        TruecallerChecker,
        GetContactChecker,
        TbankChecker,
    )

    register_checker("kaspersky", KasperskyWhoCallsChecker)
    register_checker("truecaller", TruecallerChecker)
    register_checker("getcontact", GetContactChecker)
    register_checker("tbank", TbankChecker)

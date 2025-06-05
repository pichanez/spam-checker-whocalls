from typing import Dict, Type

from .domain.phone_checker import PhoneChecker

CHECKER_REGISTRY: Dict[str, Type[PhoneChecker]] = {}


def register_checker(name: str, cls: Type[PhoneChecker]) -> None:
    """Register a checker class under a given name."""
    CHECKER_REGISTRY[name] = cls


def get_checker_class(name: str) -> Type[PhoneChecker]:
    """Retrieve a checker class by name."""
    return CHECKER_REGISTRY[name]

"""The rules of SPEC 9, one per module; each module exports RULE (Phase 5).

EQP-01 to EQP-03 need the equipment library and come with Phase 7.
"""

import importlib
import pkgutil
from functools import cache

from app.validation.core import Rule


@cache
def all_rules() -> tuple[Rule, ...]:
    found = []
    for module in pkgutil.iter_modules(__path__):
        rule = getattr(importlib.import_module(f"{__name__}.{module.name}"), "RULE", None)
        if isinstance(rule, Rule):
            found.append(rule)
    return tuple(sorted(found, key=lambda r: r.id))

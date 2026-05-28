# This file is part of the plan timetable generator, see LICENSE for details.

import os
from typing import overload


@overload
def get(name: str, default: str) -> str: ...
@overload
def get(name: str, default: None) -> str | None: ...


def get(name: str, default: str | None) -> str | None:
    return os.environ.get(name, default)


def get_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def get_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None:
        return default
    return int(value)


def get_float(name: str, default: float) -> float:
    value = os.environ.get(name)
    if value is None:
        return default
    return float(value)


def get_csv(name: str, default: list[str] | None = None) -> list[str]:
    value = os.environ.get(name)
    if value is None:
        return list(default or [])
    return [item.strip() for item in value.split(",") if item.strip()]

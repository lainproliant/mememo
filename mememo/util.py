# --------------------------------------------------------------------
# util.py
#
# Author: Lain Musgrove (lain.proliant@gmail.com)
# Date: Tuesday September 19, 2023
# --------------------------------------------------------------------

import asyncio
import functools
from datetime import timedelta

import isodate
from asgiref.sync import sync_to_async


# --------------------------------------------------------------------
def parse_td(s: str) -> timedelta:
    components = []
    day_components = []
    time_components = []
    current_component = ""

    for char in s:
        current_component += char
        if not char.isdigit():
            components.append(current_component)
            current_component = ""

    for component in components:
        match component[-1]:
            case "Y" | "y" | "M" | "D" | "d":
                day_components.append(component)
            case "h" | "m" | "s":
                time_components.append(component)
            case wrong:
                raise ValueError(f"Invalid duration component: {wrong}")

    day_part = ''.join(s.upper() for s in day_components)
    time_part = ''.join(s.upper() for s in time_components)

    return isodate.parse_duration(f"P{day_part}T{time_part}")


# --------------------------------------------------------------------
def django_sync(f):
    @functools.wraps(f)
    async def wrapper(*args, **kwargs):
        if asyncio.iscoroutinefunction(f):
            raise ValueError("Coroutine function can't be wrapped with django_sync.")
        return await sync_to_async(f)(*args, **kwargs)

    return wrapper

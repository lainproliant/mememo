# --------------------------------------------------------------------
# util.py
#
# Author: Lain Musgrove (lain.proliant@gmail.com)
# Date: Tuesday September 19, 2023
# --------------------------------------------------------------------

import asyncio
import functools
import io
from datetime import timedelta
from typing import Optional

import isodate
from asgiref.sync import sync_to_async
from commandmap import CommandMap


# --------------------------------------------------------------------
def rt_assert(value: bool, msg: str):
    if not value:
        raise RuntimeError(msg)


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

    day_part = "".join(s.upper() for s in day_components)
    time_part = "".join(s.upper() for s in time_components)

    return isodate.parse_duration(f"P{day_part}T{time_part}")


# --------------------------------------------------------------------
def django_sync(f):
    @functools.wraps(f)
    async def wrapper(*args, **kwargs):
        if asyncio.iscoroutinefunction(f):
            return await f(*args, **kwargs)
        return await sync_to_async(f)(*args, **kwargs)

    return wrapper


# --------------------------------------------------------------------
def format_command_help(cmd_map: CommandMap, command: Optional[str] = None) -> str:
    sb = io.StringIO()
    commands = cmd_map.keys()

    if command is None:
        help_lines = []
        for fn_name in sorted(commands):
            docs: str = cmd_map.get(fn_name).__doc__.strip()
            lines = docs.splitlines(keepends=False)
            usage = lines[0][1:-1]
            oneline_help = lines[1].strip()
            help_lines.append(f"- `{usage}`")
            help_lines.append(f"  {oneline_help}")

        content = "\n".join(help_lines)
        print(content, file=sb)

    else:
        content_lines = [
            line.strip()
            for line in cmd_map.get(command).__doc__.strip().splitlines(keepends=False)
        ]
        if len(content_lines) > 0:
            content_lines[0] = f"`{content_lines[0]}`"
        for line in content_lines:
            print(line, file=sb)

    return sb.getvalue()

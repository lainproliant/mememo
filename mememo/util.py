# --------------------------------------------------------------------
# util.py
#
# Author: Lain Musgrove (lain.proliant@gmail.com)
# Date: Wednesday February 8, 2023
#
# Distributed under terms of the MIT license.
# --------------------------------------------------------------------

import os
import inspect
from typing import Any

# --------------------------------------------------------------------
def env_require(name: str) -> str:
    value = os.getenv(name)
    if value is None:
        raise ValueError(f"Missing environment variable '{name}'.")
    return value


# --------------------------------------------------------------------
def get_prefixed_methods(prefix, obj):
    return [
        getattr(obj, name)
        for name in dir(obj)
        if name.startswith(prefix) and callable(getattr(obj, name))
    ]


# --------------------------------------------------------------------
class Commands:
    @staticmethod
    def get_prefixed_methods(prefix, obj):
        return [
            getattr(obj, name)
            for name in dir(obj)
            if name.startswith(prefix) and callable(getattr(obj, name))
        ]

    def __init__(self, obj, prefix="cmd_"):
        self.map: dict[str, Any] = {}
        self.prefix = prefix
        for method in Commands.get_prefixed_methods(self.prefix, obj):
            self.define(method)

    def define(self, f):
        self.map[f.__name__.removeprefix(self.prefix)] = f

    def get(self, name) -> Any:
        if name not in self.map:
            raise ValueError(f"Command `{name}` is not defined.")
        return self.map[name]

    def list(self):
        return sorted(self.map.keys())

    def signatures(self):
        for key, value in sorted(self.map.items(), key=lambda x: x[0]):
            yield (key, inspect.signature(value))

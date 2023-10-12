# --------------------------------------------------------------------
# response.py
#
# Author: Lain Musgrove (lain.proliant@gmail.com)
# Date: Thursday October 12, 2023
# --------------------------------------------------------------------
import functools
import io
import re
from typing import Callable, Generic, TypeVar
from bivalve.logging import LogManager

# --------------------------------------------------------------------
T = TypeVar("T")
log = LogManager().get(__name__)


# --------------------------------------------------------------------
class ResponseDigestor(Generic[T]):
    def __init__(self):
        self._regex_mappings: list[tuple[str, Callable[[T, re.Match], str]]] = [
            (r"@<(.*)>", self._user_mention),
            (r"#<(.*)>", self._room_mention),
        ]

    def digest_error(self, ctx: T, content: list[str]) -> str:
        raise NotImplementedError()

    def digest_response(self, ctx: T, content: list[str]) -> str:
        sb = io.StringIO()
        for line in content:
            for rx, mapper in self._regex_mappings:
                while True:
                    result = re.sub(rx, functools.partial(mapper, ctx), line)
                    if result == line:
                        break
                    line = result
            sb.write(line)
        return sb.getvalue()

    def _user_mention(self, ctx: T, match: re.Match) -> str:
        raise NotImplementedError()

    def _room_mention(self, ctx: T, match: re.Match) -> str:
        raise NotImplementedError()

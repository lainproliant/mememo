# --------------------------------------------------------------------
# util.py
#
# Author: Lain Musgrove (lain.proliant@gmail.com)
# Date: Tuesday September 19, 2023
# --------------------------------------------------------------------

import asyncio
import functools
from asgiref.sync import sync_to_async


# --------------------------------------------------------------------
def django_sync(f):
    @functools.wraps(f)
    async def wrapper(*args, **kwargs):
        if asyncio.iscoroutinefunction(f):
            raise ValueError("Coroutine function can't be wrapped with django_sync.")
        return await sync_to_async(f)(*args, **kwargs)
    return wrapper

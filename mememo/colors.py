# --------------------------------------------------------------------
# colors.py
#
# Author: Lain Musgrove (lain.proliant@gmail.com)
# Date: Wednesday February 8, 2023
#
# Distributed under terms of the MIT license.
# --------------------------------------------------------------------

from xeno.color import color
from functools import partial

class Colors:
    greeting = partial(color, fg="white", render="dim")
    cmd = partial(color, fg="green")
    param = partial(color, fg="cyan", render="dim")
    prompt = partial(color, fg="yellow")
    error = partial(color, fg="red")

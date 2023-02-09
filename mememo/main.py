# --------------------------------------------------------------------
# main.py
#
# Author: Lain Musgrove (lain.proliant@gmail.com)
# Date: Tuesday January 17, 2023
#
# Distributed under terms of the MIT license.
# --------------------------------------------------------------------

import sys
from mememo.modules import AppModule
from xeno import SyncInjector
from typing import cast


# --------------------------------------------------------------------
def main():
    injector = SyncInjector(AppModule())

    if len(sys.argv) > 1 and sys.argv[1] == "admin":
        sys.exit(cast(int, injector.require("admin")))
    else:
        injector.require("bot")


# --------------------------------------------------------------------
if __name__ == "__main__":
    main()

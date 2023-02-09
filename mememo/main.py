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


# --------------------------------------------------------------------
def main(argv):
    injector = SyncInjector(AppModule())

    if len(argv) > 0 and argv[0] == "admin":
        injector.require("admin")
    else:
        injector.require("bot")


# --------------------------------------------------------------------
if __name__ == "__main__":
    main(sys.argv[1:])

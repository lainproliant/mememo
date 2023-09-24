# --------------------------------------------------------------------
# service.py
#
# Author: Lain Musgrove (lain.proliant@gmail.com)
# Date: Wednesday September 20, 2023
# --------------------------------------------------------------------

from dataclasses import dataclass
from dataclass_wizard import YAMLWizard

# --------------------------------------------------------------------
@dataclass
class Service(YAMLWizard):
    name: str
    script: str

# --------------------------------------------------------------------
# domain.py
#
# Author: Lain Musgrove (lain.proliant@gmail.com)
# Date: Wednesday February 8, 2023
#
# Distributed under terms of the MIT license.
# --------------------------------------------------------------------

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

# --------------------------------------------------------------------
@dataclass
class Topic:
    name: str
    script_path: Path
    last_updated_timestamp: datetime = datetime.min
    update_freq_minutes: int = 30
    id: int = -1


# --------------------------------------------------------------------
@dataclass
class Subscription:
    topic_id: int
    user_id: int


# --------------------------------------------------------------------
@dataclass
class UserInfo:
    id: int
    username: str

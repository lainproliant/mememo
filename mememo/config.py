# --------------------------------------------------------------------
# config.py
#
# Author: Lain Musgrove (lain.musgrove@hearst.com)
# Date: Sunday October 8, 2023
# --------------------------------------------------------------------

from dataclasses import dataclass
from dataclass_wizard import YAMLWizard
from typing import Optional


# --------------------------------------------------------------------
@dataclass
class DiscordConfig(YAMLWizard):
    enabled: bool
    token: str
    mememo_user: str
    mememo_passwd: str


# --------------------------------------------------------------------
@dataclass
class AgentConfig(YAMLWizard):
    log_level: str


# --------------------------------------------------------------------
@dataclass
class Config(YAMLWizard):
    agent: AgentConfig
    discord: DiscordConfig
    env: dict[str, str]

    @classmethod
    def load(cls):
        cls.INSTANCE = cls.from_file("/opt/mememo/config.yaml")
        for key, value in cls.INSTANCE.env.items():
            os.environ[key] = value

    @classmethod
    def get(cls) -> "Config":
        if cls.INSTANCE is None:
            cls.load()
        return cls.INSTANCE


Config.INSTANCE: Optional[Config] = None

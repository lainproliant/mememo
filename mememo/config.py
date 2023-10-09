# --------------------------------------------------------------------
# config.py
#
# Author: Lain Musgrove (lain.musgrove@hearst.com)
# Date: Sunday October 8, 2023
# --------------------------------------------------------------------

import os
import sys
import traceback
from dataclasses import dataclass
from datetime import timedelta
from typing import cast

from dataclass_wizard import YAMLWizard

from mememo.util import parse_td


# --------------------------------------------------------------------
@dataclass
class DiscordConfig(YAMLWizard):
    enabled: bool = False
    token: str = "your-discord-bot-token-here"
    mememo_user: str = "discord-agent"
    mememo_passwd: str = "agent-password-here"


# --------------------------------------------------------------------
@dataclass
class ThirdPartyAuthConfig(YAMLWizard):
    challenge_expiry: str = "1h"
    expiry: str = "90d"

    def get_challenge_expiry(self) -> timedelta:
        return parse_td(self.challenge_expiry)

    def get_expiry(self) -> timedelta:
        return parse_td(self.expiry)


# --------------------------------------------------------------------
@dataclass
class AgentConfig(YAMLWizard):
    log_level: str = "INFO"
    host: str = "0.0.0.0"
    port: int = 8510
    timeout: str = "5m"

    def get_timeout(self) -> timedelta:
        return parse_td(self.timeout)


# --------------------------------------------------------------------
@dataclass
class Config(YAMLWizard):
    agent: AgentConfig = AgentConfig()
    auth3p: ThirdPartyAuthConfig = ThirdPartyAuthConfig()
    discord: DiscordConfig = DiscordConfig()
    env: dict[str, str] = {}

    @classmethod
    def load(cls):
        try:
            cls.INSTANCE = cls.from_yaml_file("/opt/mememo/config.yaml")
        except Exception:
            traceback.print_exc()
            print("Couldn't load configs, using default values.", file=sys.stderr)
            cls.INSTANCE = Config()

        for key, value in cls.INSTANCE.env.items():
            os.environ[key] = value

    @classmethod
    def get(cls) -> "Config":
        if cls.INSTANCE is None:
            cls.load()
        return cast("Config", cls.INSTANCE)


Config.INSTANCE = None

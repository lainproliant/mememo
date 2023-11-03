# --------------------------------------------------------------------
# config.py
#
# Author: Lain Musgrove (lain.musgrove@hearst.com)
# Date: Sunday October 8, 2023
# --------------------------------------------------------------------

import locale
import os
import sys
import traceback
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Optional, cast

from dataclass_wizard import YAMLWizard

from mememo.util import parse_td


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
class Auth3pConfig(YAMLWizard):
    challenge_expiry: str = "1h"
    expiry: str = "90d"

    def get_challenge_expiry(self) -> timedelta:
        return parse_td(self.challenge_expiry)

    def get_expiry(self) -> timedelta:
        return parse_td(self.expiry)


# --------------------------------------------------------------------
@dataclass
class DiscordConfig(YAMLWizard):
    enabled: bool = False
    token: str = "your-discord-bot-token-here"
    timeout: str = "120s"
    mememo_user: str = "discord-agent"
    mememo_passwd: str = "agent-password-here"
    sigil: str = "!mememo"

    def get_client_timeout(self) -> int:
        return parse_td(self.timeout).total_seconds()


# --------------------------------------------------------------------
@dataclass
class ThirdPartyServiceDefinition(YAMLWizard):
    repo: str
    run: str
    handles: str
    env: dict[str, str]
    setup: str = ""
    cache: Optional[str] = None
    refresh: Optional[str] = None
    schedule: Optional[str] = None
    required_grants: list[str] = field(default_factory=list)
    doc: Optional[str] = None
    catchup = False
    enabled = False

    def get_cache_duration(self) -> Optional[timedelta]:
        if self.cache is None:
            return None
        return parse_td(self.cache)

    def get_refresh_interval(self) -> Optional[timedelta]:
        if self.refresh is None:
            return None
        return parse_td(self.refresh)


# --------------------------------------------------------------------
@dataclass
class SystemConfig(YAMLWizard):
    service_grant_expiry: str = "90d"
    config_refresh: str = "5m"
    service_update: str = "1m"

    def get_service_grant_expiry(self) -> timedelta:
        return parse_td(self.service_grant_expiry)

    def get_config_refresh_delay(self) -> timedelta:
        return parse_td(self.config_refresh)

    def get_service_update_delay(self) -> timedelta:
        return parse_td(self.service_update)


# --------------------------------------------------------------------
@dataclass
class Config(YAMLWizard):
    agent: AgentConfig = field(default_factory=AgentConfig)
    system: SystemConfig = field(default_factory=SystemConfig)
    auth3p: Auth3pConfig = field(default_factory=Auth3pConfig)
    discord: DiscordConfig = field(default_factory=DiscordConfig)
    services: dict[str, ThirdPartyServiceDefinition] = field(default_factory=dict)
    env: dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        locale.setlocale(locale.LC_ALL, "")

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
    def reload(cls):
        cls.INSTANCE = None
        cls.load()

    @classmethod
    def get(cls) -> "Config":
        if cls.INSTANCE is None:
            cls.load()
        return cast("Config", cls.INSTANCE)


Config.INSTANCE = None

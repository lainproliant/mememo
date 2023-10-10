# --------------------------------------------------------------------
# config.py
#
# Author: Lain Musgrove (lain.musgrove@hearst.com)
# Date: Sunday October 8, 2023
# --------------------------------------------------------------------

import os
import sys
import traceback
from dataclasses import dataclass, field
from datetime import timedelta
from typing import cast, Optional

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
    mememo_user: str = "discord-agent"
    mememo_passwd: str = "agent-password-here"


# --------------------------------------------------------------------
@dataclass
class ServiceDefinition(YAMLWizard):
    repo: str
    run: str
    handles: str
    env: dict[str, str]
    setup: str = ""
    cache: Optional[str] = None
    schedule: Optional[str] = None
    catchup = False
    enabled = False

    def get_cache_duration(self) -> Optional[timedelta]:
        if self.cache is None:
            return None
        return parse_td(self.cache)


# --------------------------------------------------------------------
@dataclass
class ServiceConfig(YAMLWizard):
    services: dict[str, ServiceDefinition] = field(default_factory=dict)


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
    services: ServiceConfig = field(default_factory=ServiceConfig)
    env: dict[str, str] = field(default_factory=dict)

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

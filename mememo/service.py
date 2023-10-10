# --------------------------------------------------------------------
# service.py
#
# Author: Lain Musgrove (lain.proliant@gmail.com)
# Date: Wednesday September 20, 2023
# --------------------------------------------------------------------

import asyncio
from io import StringIO
from datetime import datetime, timedelta
from pathlib import Path

import croniter

from xeno.shell import Shell
from mememo.config import ServiceDefinition, Config
from bivalve.logging import LogManager
from typing import Iterable, Optional

# --------------------------------------------------------------------
BASE_PATH = Path("/opt/mememo/services")
RESULTS_FILE = Path("results.txt")

log = LogManager.get(__name__)


# --------------------------------------------------------------------
class Service:
    def __init__(self, name: str, definition: ServiceDefinition):
        self.name = name
        self.definition = definition
        self.log = log.getChild(name)

    def base_path(self) -> Path:
        return BASE_PATH / self.name

    def cached_result_path(self) -> Path:
        return self.base_path() / RESULTS_FILE

    def cache_duration(self) -> Optional[timedelta]:
        return self.definition.get_cache_duration()

    def cached_result_age(self, ref: datetime) -> timedelta:
        if not self.cached_result_path().exists():
            return timedelta.max
        return ref - datetime.fromtimestamp(self.cached_result_path().stat().st_mtime)

    def cached_result(self) -> Optional[str]:
        now = datetime.now()

        cache_duration = self.cache_duration()
        if cache_duration is None:
            return None

        if self.cached_result_age(now) > cache_duration:
            self.cached_result_path().unlink(missing_ok=True)
            return None

        with open(self.cached_result_path(), "r") as infile:
            return infile.read()

    def enabled(self):
        return self.definition.enabled

    def next_update_time(self, ref: datetime) -> datetime:
        if self.definition.schedule is None:
            return datetime.max

        if not croniter.is_valid(self.definition.schedule):
            raise ValueError(
                f"Service {self.name} has an invalid cron schedule: {self.definition.schedule}"
            )
        cron = croniter.croniter(self.definition.schedule, ref)
        return cron.get_next(datetime)

    async def prepare(self):
        sh = Shell().cd(BASE_PATH)

        if not self.base_path().exists():
            self.log.info(f"Cloning: {self.definition.repo}")
            await sh.run("git clone {repo}", repo=self.definition.repo, check=True)

        else:
            self.log.info("Forcing git pull update: {self.definition.repo}")
            await sh.cd(self.base_path()).run(
                "git fetch --all && git reset --hard @{u}", check=True
            )

        if self.definition.setup:
            self.log.info("Running setup command: {self.definition.setup}")
            await sh.cd(self.base_path()).run(self.definition.setup, check=True)

    async def update(self) -> str:
        cached_result = self.cached_result()
        if cached_result is not None:
            return cached_result

        sb = StringIO()

        def on_line(s: str, _):
            sb.write(s)

        sh = Shell(self.definition.env, self.base_path())
        await sh.run(self.definition.run, stdout=on_line, check=True)

        if self.cache_duration() is not None:
            with open(self.cached_result_path(), "w") as outfile:
                outfile.write(sb.getvalue())

        return sb.getvalue()


# --------------------------------------------------------------------
class ServiceManager:
    def __init__(self):
        self.next_update_dt = datetime.min
        self.last_update_dt = datetime.min
        BASE_PATH.mkdir(parents=True, exist_ok=True)

    def services(self) -> Iterable[Service]:
        for name, definition in Config.get().services.items():
            yield Service(name, definition)

    async def scheduled_update(self):
        now = datetime.now()
        while self.next_update_dt < now:
            update_delay = (
                Config.get().system.get_service_update_delay().total_seconds()
            )
            await asyncio.sleep(update_delay)
            now = datetime.now()

        await self.update()

    async def update(self):
        now = datetime.now()

        for service in self.services():
            if service.next_update_time():
                pass # TODO!

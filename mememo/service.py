# --------------------------------------------------------------------
# service.py
#
# Author: Lain Musgrove (lain.proliant@gmail.com)
# Date: Wednesday September 20, 2023
# --------------------------------------------------------------------

import asyncio
import re
import shlex
from dataclasses import dataclass
from datetime import datetime, timedelta
from io import StringIO
from pathlib import Path
from typing import Iterable, Optional

import croniter
from bivalve.logging import LogManager
from django.contrib.auth.models import User
from xeno.shell import Shell

from mememo.config import Config, ServiceDefinition
from mememo.util import django_sync
from mememo.models import ServiceGrant
from mememo.models import new_id

# --------------------------------------------------------------------
BASE_PATH = Path("/opt/mememo/services")
RESULTS_FILE = Path("results.txt")
INSTANCE_FILE = Path("instance.id")
LAST_UPDATE_FILE = Path("last_update.dt")
NEXT_UPDATE_FILE = Path("next_update.dt")

log = LogManager().get(__name__)


# --------------------------------------------------------------------
@dataclass
class ServiceCallContext:
    user: User
    service_name: str
    args: list[str]

    def get_permissions(self) -> set[str]:
        return self.user.get_all_permissions()

    def get_grants(self) -> set[str]:
        return ServiceGrant.by_user(self.user)

    def to_env(self) -> dict[str, str]:
        return {
            "MEMEMO_USERNAME": self.user.username,
            "MEMEMO_EMAIL": self.user.email,
            "MEMEMO_PERMISSIONS": shlex.join(self.user.get_all_permissions()),
            "MEMEMO_GRANTS": ",".join(self.get_grants()),
            "MEMEMO_FUNCTION": self.service_name,
            "MEMEMO_ARGS": shlex.join(self.args),
        }


# --------------------------------------------------------------------
class TimestampedBasePath:
    def base_path(self):
        raise NotImplementedError()

    @property
    def last_update_dt(self) -> datetime:
        last_update_file = self.base_path() / LAST_UPDATE_FILE
        if not last_update_file.exists():
            return datetime.min
        try:
            return datetime.fromisoformat(open(last_update_file, "r").read())
        except Exception:
            return datetime.min

    @last_update_dt.setter
    def last_update_dt(self, dt: datetime):
        last_update_file = self.base_path() / LAST_UPDATE_FILE
        open(last_update_file, "w").write(dt.isoformat())

    @property
    def next_update_dt(self) -> datetime:
        next_update_file = self.base_path() / NEXT_UPDATE_FILE
        if not next_update_file.exists():
            return datetime.now()
        try:
            return datetime.fromisoformat(open(next_update_file, "r").read())
        except Exception:
            return datetime.now()

    @next_update_dt.setter
    def next_update_dt(self, dt: datetime):
        next_update_file = self.base_path() / NEXT_UPDATE_FILE
        open(next_update_file, "w").write(dt.isoformat())


# --------------------------------------------------------------------
class Service:
    def __init__(self, name: Optional[str] = None):
        self.name = name or (self.__class__.__module__ + self.__class__.__qualname__)
        self.log = log.getChild(name)

    def handles_function(self, fn_name: str) -> bool:
        raise NotImplementedError()

    def handles_message(self, message: str) -> bool:
        return False

    async def prepare(self, instance_id: str, ctx: Optional[ServiceCallContext] = None):
        pass

    async def invoke(
        self, instance_id: str, ctx: Optional[ServiceCallContext] = None
    ) -> str:
        raise NotImplementedError()


# --------------------------------------------------------------------
class ThirdPartyService(Service, TimestampedBasePath):
    def __init__(self, name: str, definition: ServiceDefinition):
        self.name = name
        self.definition = definition
        self.log = log.getChild(name)

    def log_stdout(self, s: str, _):
        self.log.info(f"> {s}")

    def log_stderr(self, s: str, _):
        self.log.warning(f"> {s}")

    def base_path(self) -> Path:
        return BASE_PATH / self.name

    def cached_result_path(self) -> Path:
        return self.base_path() / RESULTS_FILE

    def instance_file_path(self) -> Path:
        return self.base_path() / INSTANCE_FILE

    def handles(self, fn_name: str) -> bool:
        return re.compile(self.definition.handles).match(fn_name) is not None

    @property
    def instance_id(self) -> str:
        if not self.instance_file_path().exists():
            return "never"
        with open(self.instance_file_path(), "r") as infile:
            return infile.read()

    @instance_id.setter
    def instance_id(self, instance_id):
        with open(self.instance_file_path(), "w") as outfile:
            outfile.write(instance_id)

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

    async def refresh(self):
        await self._git_pull()
        await self._setup()

    async def prepare(self, instance_id: str, ctx: Optional[ServiceCallContext] = None):
        if ctx is not None:
            await django_sync(self._check_service_grants)(ctx)

        if not self.base_path().exists():
            await self._git_clone()
            await self._setup()

        if self.instance_id != instance_id:
            await self._setup()
            self.instance_id = instance_id

    async def invoke(
        self, instance_id: str, ctx: Optional[ServiceCallContext] = None
    ) -> str:
        if ctx is not None:
            await django_sync(self._check_service_grants)(ctx)

        cached_result = self.cached_result()
        if cached_result is not None:
            return cached_result

        sh = (
            Shell()
            .cd(self.base_path())
            .env(self.definition.env)
            .env({"GIT_TERMINAL_PROMPT": "0"})
        )
        sb = StringIO()

        def stdout_sink(s: str, _):
            print(s, file=sb)

        if ctx is not None:
            sh = sh.env(await django_sync(ctx.to_env)())

        await sh.run(
            self.definition.run,
            stdout=stdout_sink,
            stderr=self.log_stderr,
            check=True,
        )

        if self.cache_duration() is not None:
            with open(self.cached_result_path(), "w") as outfile:
                outfile.write(sb.getvalue())

        return sb.getvalue()

    def _check_service_grants(self, ctx: ServiceCallContext):
        if ctx.user.is_superuser:
            return
        grants = ctx.get_grants()
        missing_grants = []
        for grant in self.definition.required_grants:
            if grant not in grants:
                missing_grants.append(grant)
        if missing_grants:
            raise RuntimeError(
                f"Missing required service grants: {', '.join(missing_grants)}"
            )

    def _sh(self):
        return (
            Shell()
            .cd(BASE_PATH)
            .env(self.definition.env)
            .env({"GIT_TERMINAL_PROMPT": "0"})
        )

    async def _git_clone(self):
        self.log.info(f"Cloning: {self.definition.repo}")
        await self._sh().run(
            "git clone {repo} {dest}",
            repo=self.definition.repo,
            dest=self.base_path(),
            stdout=self.log_stdout,
            stderr=self.log_stderr,
            check=True,
        )

    async def _git_pull(self):
        self.log.info(f"Forcing git pull update: {self.definition.repo}")
        await self._sh().cd(self.base_path()).run(
            "git fetch --all && git reset --hard @{{u}}",
            check=True,
            stdout=self.log_stdout,
            stderr=self.log_stderr,
        )

    async def _setup(self):
        if not self.definition.setup:
            return

        self.log.info(f"Running setup command: {self.definition.setup}")
        await self._sh().cd(self.base_path()).run(
            self.definition.setup,
            check=True,
            stdout=self.log_stdout,
            stderr=self.log_stderr,
        )


# --------------------------------------------------------------------
class ServiceManager(TimestampedBasePath):
    def __init__(self):
        self.base_path().mkdir(parents=True, exist_ok=True)
        self.services: list[Service] = []
        self.instance_id = new_id()

    def install(self, svc: Service):
        self.services.append(svc)

    def base_path(self):
        return BASE_PATH

    def third_party_services(self) -> Iterable[ThirdPartyService]:
        for name, definition in Config.get().services.items():
            yield ThirdPartyService(name, definition)

    def services(self) -> Iterable[Service]:
        yield from self.third_party_services()
        yield from self.services

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

        for service in self.third_party_services():
            if service.next_update_time(self.last_update_dt) < now:
                await service.prepare(self.instance_id)
                await service.invoke(self.instance_id)

        self.last_update_dt = datetime.now()
        self.next_update_dt = now + Config().get().system.get_service_update_delay()

    def has_message_handler(self, message: str) -> Service:
        try:
            self.get_message_handler(message)
            return True

        except NotImplementedError:
            return False

    def get_message_handler(self, message: str) -> Service:
        for service in self.services():
            if service.handles_message(message):
                return service
        raise NotImplementedError()

    def get_function_handler(self, fn_name: str) -> Service:
        for service in self.services():
            if service.handles(fn_name):
                return service
        raise NotImplementedError()

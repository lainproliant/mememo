# --------------------------------------------------------------------
# runagent.py
#
# Author: Lain Musgrove (lain.proliant@gmail.com)
# Date: Wednesday September 13, 2023
# --------------------------------------------------------------------

import asyncio
import signal

from bivalve.agent import BivalveAgent
from django.core.management.base import BaseCommand
from ledger.service import LedgerService
from mememo.agent import MememoAgent
from mememo.config import Config
from mememo.discord.bot import DiscordAgent
from mememo.service import ServiceManager
from task.service import TaskService
from waterlog import LogManager

# --------------------------------------------------------------------
config = Config.get()
LogManager().setup()
LogManager().set_level(config.agent.log_level)
LogManager().set_format(
    "%(asctime)s @ %(pathname)s:%(lineno)d:%(funcName)s\n[%(levelname)s] %(message)s"
)
log = LogManager().get(__name__)


# --------------------------------------------------------------------
class Command(BaseCommand):
    help = "Start the Bivalve Agent for local IPC."

    async def _run_agents(self, agents: list[BivalveAgent]):
        def ctrlc(*_):
            log.critical("Ctrl+C received.")
            for agent in agents:
                agent.shutdown()

        signal.signal(signal.SIGINT, ctrlc)
        await asyncio.gather(*[agent.run() for agent in agents])

    def handle(self, *args, **kwargs):
        service_manager = ServiceManager()
        service_manager.install(LedgerService())
        service_manager.install(TaskService())

        main_agent = MememoAgent(service_manager, config.agent.host, config.agent.port)
        agents = [main_agent]
        if config.discord.enabled:
            agents.append(DiscordAgent(service_manager, main_agent))

        asyncio.run(self._run_agents(agents))

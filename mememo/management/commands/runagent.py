# --------------------------------------------------------------------
# runagent.py
#
# Author: Lain Musgrove (lain.proliant@gmail.com)
# Date: Wednesday September 13, 2023
# --------------------------------------------------------------------

import asyncio
import logging
import signal

from bivalve.logging import LogManager
from config.settings import AGENT_LOG_LEVEL, AGENT_UNIX_SOCKET_PATH
from django.core.management.base import BaseCommand
from mememo.agent import MememoAgent
from mememo.discord import DiscordAgent

# --------------------------------------------------------------------
LogManager().setup()
LogManager().set_level(AGENT_LOG_LEVEL)
LogManager().set_format(
    "%(asctime)s @ %(pathname)s:%(lineno)d:%(funcName)s\n[%(levelname)s] %(message)s"
)
log = LogManager().get(__name__)


# --------------------------------------------------------------------
class Command(BaseCommand):
    help = "Start the Bivalve Agent for local IPC."

    async def _run_agents(self, agents: list[MememoAgent]):
        def ctrlc(*_):
            log.critical("Ctrl+C received.")
            for agent in agents:
                agent.shutdown()

        signal.signal(signal.SIGINT, ctrlc)
        await asyncio.gather(*[agent.run() for agent in agents])

    def handle(self, *args, **kwargs):
        main_agent = MememoAgent(AGENT_UNIX_SOCKET_PATH)
        agents = [main_agent]
        if DiscordAgent.ENABLED:
            agents.append(DiscordAgent(main_agent))

        asyncio.run(self._run_agents(agents))

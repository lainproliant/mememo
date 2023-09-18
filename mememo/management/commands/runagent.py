# --------------------------------------------------------------------
# runagent.py
#
# Author: Lain Musgrove (lain.proliant@gmail.com)
# Date: Wednesday September 13, 2023
# --------------------------------------------------------------------

import asyncio
from django.core.management.base import BaseCommand
from config.settings import AGENT_UNIX_SOCKET_PATH
from mememo.agent import MememoAgent
from mememo.bot import MememoBot


class Command(BaseCommand):
    help = "Start the Bivalve Agent for local IPC."

    async def _run_agent_and_bot(self):
        agent = MememoAgent(AGENT_UNIX_SOCKET_PATH)
        bot = MememoBot(agent)
        await asyncio.gather(agent.run(), bot.start())

    def handle(self, *args, **kwargs):
        asyncio.run(self._run_agent_and_bot())

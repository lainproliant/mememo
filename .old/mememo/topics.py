# --------------------------------------------------------------------
# topics.py
#
# Author: Lain Musgrove (lain.proliant@gmail.com)
# Date: Wednesday February 8, 2023
#
# Distributed under terms of the MIT license.
# --------------------------------------------------------------------
import discord

from domain import Topic
from datetime import datetime
from discord.ext import commands, tasks


# --------------------------------------------------------------------
class TopicRunner:
    def __init__(self, topic: Topic, last_updated: datetime = datetime.min):
        self.topic = topic

    def run(self):
        # TODO: Run and see if there's any output.
        pass


# --------------------------------------------------------------------
class TopicUpdateService(commands.Cog):
    def __init__(self, bot: discord.Client):
        self.bot = bot
        self.update_task.start()
        self.runners: dict[str, TopicRunner] = {}

    def cog_unload(self):
        self.update_task.cancel()

    @tasks.loop(minutes=5.0)
    async def update_task(self):
        async with self.bot.pool.acquire() as con:
            pass

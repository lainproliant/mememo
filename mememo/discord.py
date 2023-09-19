# --------------------------------------------------------------------
# discord.py
#
# Author: Lain Musgrove (lain.proliant@gmail.com)
# Date: Wednesday September 13, 2023
# --------------------------------------------------------------------

import shlex

import asyncio
import environ
from bivalve.agent import BivalveAgent
from bivalve.logging import LogManager

import discord
from mememo.agent import MememoAgent

# --------------------------------------------------------------------
env = environ.Env(MEMEMO_BOT_ENABLED=(bool, False))
log = LogManager().get(__name__)


# --------------------------------------------------------------------
class DiscordAgent(BivalveAgent):
    ENABLED = env("MEMEMO_DISCORD_ENABLED")
    TOKEN = env("MEMEMO_DISCORD_TOKEN")
    AGENT_USERNAME = env("MEMEMO_DISCORD_AGENT_USERNAME")
    AGENT_PASSWORD = env("MEMEMO_DISCORD_AGENT_PASSWORD")

    def __init__(self, peer: MememoAgent):
        super().__init__()
        self.bot = DiscordClient(self)
        self.peer = peer

    async def run(self):
        self.add_connection(self.peer.bridge())
        await asyncio.gather(super().run(), self.bot.start(self.TOKEN))

    async def on_connect(self, _):
        result = await self.call("auth", self.AGENT_USERNAME, self.AGENT_PASSWORD)
        if result.code != result.Code.OK:
            log.critical(f"Discord agent authentication failed: {result}")
            self.shutdown()
        else:
            log.info("Discord agent successfully authenticated.")

    def on_disconnect(self, _):
        self.schedule(self.bot.close())
        self.shutdown()


# --------------------------------------------------------------------
class DiscordClient(discord.Client):
    def __init__(self, agent: DiscordAgent):
        super().__init__(
            intents=discord.Intents(messages=True, message_content=True, typing=True),
        )
        self.agent = agent

    async def on_message(self, message):
        if message.author == self.user:
            return

        if self.user in message.mentions or isinstance(
            message.channel, discord.DMChannel
        ):
            fn_name, *argv = [
                x for x in shlex.split(message.content) if x != self.user.mention
            ]

            if fn_name == "auth":
                fn_name = "auth3p"

            try:
                result = await self.agent.call(
                    fn_name,
                    "discord-" + str(message.author.id),
                    message.author.name,
                    *argv,
                )
                await message.channel.send(f"```\n{repr(result.__dict__)}```")

            except Exception as e:
                await message.channel.send(
                    f"I'm sorry, an error occurred.\n`{e.__class__.__qualname__}: {e}`"
                )

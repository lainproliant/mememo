# --------------------------------------------------------------------
# bot.py
#
# Author: Lain Musgrove (lain.proliant@gmail.com)
# Date: Wednesday September 13, 2023
# --------------------------------------------------------------------

import shlex

import discord
from bivalve.agent import BivalveAgent
from mememo.agent import MememoAgent


# --------------------------------------------------------------------
class BotAgent(BivalveAgent):
    def __init__(self, peer: MememoAgent, *args, **kwargs):
        super().__init__()
        self.bot = MememoBot(self, *args, **kwargs)
        self.peer = peer
        peer_conn = self.peer.bridge()
        self.peer_id = peer_conn.id
        self.add_connection(peer_conn)

    def on_disconnect(self, _):
        super().on_disconnect()
        self.bot.close()
        self.shutdown()


# --------------------------------------------------------------------
class MememoBot(discord.Client):
    def __init__(self, agent: MememoAgent, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client = BivalveAgent()
        self.client.add_connection(agent.bridge())

    async def on_message(self, message):
        if message.author == self.user:
            return

        if self.user in message.mentions:
            argv = [x for x in shlex.split(message.content) if x != self.user.mention]
            try:
                result = await self.client.call(*argv)
                message.channel.send(f"```\n{repr(result.__dict__)}```")

            except Exception as e:
                await message.channel.send(f"I'm sorry, an error occurred.\n`{e}`")

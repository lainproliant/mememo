# --------------------------------------------------------------------
# bot.py
#
# Author: Lain Musgrove (lain.proliant@gmail.com)
# Date: Wednesday February 8, 2023
#
# Distributed under terms of the MIT license.
# --------------------------------------------------------------------
import shlex

import discord

from mememo.db import DAOFactory
from mememo.util import Commands


# --------------------------------------------------------------------
class MememoBotClient(discord.Client):
    def __init__(self, dao: DAOFactory, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.dao = dao
        self.commands = Commands(self)

    async def respond(self, message, text):
        await message.channel.send(f"Hi {message.author.name}! " + text)

    async def cmd_topics(self, message, *args):
        topics = self.dao.topics().list_names()

        if not topics:
            await self.respond(message, "No topics are available to subscribe to yet.")
            return

        await self.respond(message, f"These are the available topics: {topics}")

    async def cmd_subscribe(self, message, topic):
        await self.respond(
            message,
            f"I would like to subscribe you to topic {topic}, but I don't know how to do that yet.",
        )

    async def cmd_unsubscribe(self, message, topic):
        await self.respond(message, "I don't know how to do that yet.")

    async def cmd_whoami(self, message):
        await self.respond(
            message, f"You are {message.author}, with id {message.author.id}"
        )

    async def on_ready(self):
        print(f"{self.user} has connected to Discord!")

    async def on_message(self, message):
        if message.author == self.user:
            return

        if self.user in message.mentions:
            argv = [x for x in shlex.split(message.content) if x != self.user.mention]
            try:
                await self.commands.get(argv[0])(message, *argv[1:])

            except Exception as e:
                await message.channel.send(f"I'm sorry, {e}")

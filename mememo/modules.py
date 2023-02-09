# --------------------------------------------------------------------
# modules.py
#
# Author: Lain Musgrove (lain.proliant@gmail.com)
# Date: Wednesday February 8, 2023
#
# Distributed under terms of the MIT license.
# --------------------------------------------------------------------

import readline

import discord
from dotenv import load_dotenv
from xeno import provide, singleton

from mememo.admin import AdminCommandInterface
from mememo.bot import MememoBotClient
from mememo.db import SQLiteDAOFactory
from mememo.util import env_require


# --------------------------------------------------------------------
class AppModule:
    @singleton
    def readline_init(self):
        readline.parse_and_bind("tab: complete")
        readline.parse_and_bind("set editing-mode vi")

    @singleton
    def dotenv(self):
        load_dotenv()

    @provide
    def db_filename(self, dotenv):
        return env_require("MEMEMO_DB")

    @provide
    def access_token(self, dotenv):
        return env_require("DISCORD_TOKEN")

    @provide
    def dao_factory(self, db_filename):
        return SQLiteDAOFactory(db_filename)

    @singleton
    def bot(self, dao_factory, access_token):
        intents = discord.Intents(messages=True, message_content=True, typing=True)
        bot = MememoBotClient(dao_factory, intents=intents)
        bot.run(access_token)

    @singleton
    def admin(self, readline_init, dao_factory):
        admin = AdminCommandInterface(dao_factory)
        readline.set_completer(admin.readline_cmd_complete)
        admin.run()

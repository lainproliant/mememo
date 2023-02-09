# --------------------------------------------------------------------
# admin.py
#
# Author: Lain Musgrove (lain.proliant@gmail.com)
# Date: Wednesday February 8, 2023
#
# Distributed under terms of the MIT license.
# --------------------------------------------------------------------

import os
import shlex
import sys

from mememo.colors import Colors as C
from mememo.db import DAOFactory
from mememo.domain import Topic
from mememo.strings import ADMIN_INTRO
from mememo.util import Commands


# --------------------------------------------------------------------
class AdminCommandInterface:
    def __init__(self, dao: DAOFactory):
        self.dao = dao
        self.commands = Commands(self)

    def cmd_create_topic(self, topic_name, script_path):
        if topic_name in self.dao.topics().list_names():
            raise ValueError("Topic already exists.")
        if not os.path.exists(script_path):
            raise ValueError("Script path does not exist.")
        if not os.access(script_path, os.X_OK):
            raise ValueError("Script path is not executable.")

        topic = Topic(topic_name, script_path)
        self.dao.topics().create(topic)
        print(f"Created {topic}.")

    def cmd_quit(self):
        print(C.greeting("Goodbye."))
        sys.exit(0)

    def cmd_help(self):
        for key, signature in self.commands.signatures():
            print(f"{C.cmd(key)} {C.param(' '.join(signature.parameters))}")

    def readline_cmd_complete(self, text, state):
        matches = self.commands.list()

        if text:
            matches = [m for m in matches if m.startswith(text)]

        try:
            return matches[state]
        except IndexError:
            return None

    def run(self):
        print(C.greeting(ADMIN_INTRO))
        while True:
            try:
                s = input(C.prompt("admin> "))
                if not s:
                    continue
                argv = shlex.split(s)
                self.commands.get(argv[0])(*argv[1:])

            except Exception as e:
                print(f"{C.error('ERROR:')} {C.error(str(e))}")

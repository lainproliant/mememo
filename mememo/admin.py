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
        self.dirty = False
        self.echo = True
        self.dao = dao
        self.commands = Commands(self)
        self.hidden_commands = Commands(self, prefix="hidden_cmd_")

    def cmd_create_topic(self, topic_name, script_path):
        if topic_name in self.dao.topics().list_names():
            raise ValueError("Topic already exists.")
        if not os.path.exists(script_path):
            raise ValueError("Script path does not exist.")
        if not os.access(script_path, os.X_OK):
            raise ValueError("Script path is not executable.")

        topic = Topic(topic_name, os.path.abspath(script_path))
        self.dao.topics().create(topic)
        print(f"Created {topic}.")
        self.dirty = True

    def cmd_quit(self):
        print(C.greeting("Goodbye."))
        sys.exit(0)

    def cmd_list_topics(self):
        topics = self.dao.topics().list()
        for topic in topics:
            print(topic)

    def cmd_help(self):
        for key, signature in self.commands.signatures():
            print(f"{C.cmd(key)} {C.param(' '.join(signature.parameters))}")

    def cmd_run_script(self, filename):
        with open(filename, 'r') as infile:
            for line in infile:
                if self.echo and not line.startswith('@'):
                    print(C.greeting('>'), C.greeting(line.strip()))
                self.exec(shlex.split(line), rethrow=False)

    def cmd_echo(self, *args):
        print(*args)

    def hidden_cmd_echo(self, onoff):
        if onoff == "on":
            self.echo = True
        elif onoff == "off":
            self.echo = False
        else:
            raise ValueError("Invalid parameter for echo command.")

    def readline_cmd_complete(self, text, state):
        matches = self.commands.list()

        if text:
            matches = [m for m in matches if m.startswith(text)]

        try:
            return matches[state]
        except IndexError:
            return None

    def exec(self, argv, rethrow=True):
        try:
            if argv[0].startswith('@'):
                self.hidden_commands.get(argv[0][1:])(*argv[1:])

            else:
                self.commands.get(argv[0])(*argv[1:])

        except Exception as e:
            if self.echo:
                print(f"{C.error('ERROR:')} {C.error(str(e))}")
            if rethrow:
                raise e

    def run(self, argv) -> int:
        if not argv:
            print(C.greeting(ADMIN_INTRO))
            while True:
                s = input(C.prompt("admin> "))
                if not s:
                    continue
                argv = shlex.split(s)
                self.exec(argv, rethrow=False)
        else:
            try:
                self.exec(argv)
            except Exception:
                return 1
        return 0

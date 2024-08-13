# --------------------------------------------------------------------
# service.py
#
# Author: Lain Musgrove (lain.proliant@gmail.com)
# Date: Sunday June 30, 2024
# --------------------------------------------------------------------

import argparse
import io
from dataclasses import dataclass
from typing import Iterable, Optional

import tabulate
from commandmap import CommandMap
from django.contrib.auth.models import User
from django.db import transaction
from mememo.service import Service, ServiceCallContext
from mememo.util import django_sync, format_command_help, rt_assert

from task.models import Project, ProjectAccess, Task, TaskUpdate

# --------------------------------------------------------------------
TABLE_WIDTH = 70
DATE_FORMAT = "%Y-%m-%d"
INIT_STATUS = "INIT"
START_STATUS = "TODO"


# --------------------------------------------------------------------
@dataclass
class Config:
    proj: Optional[str] = None
    status: Optional[list[str]] = None
    not_status: Optional[list[str]] = None
    participant: bool = False
    owner: bool = False
    user: Optional[str] = None
    args: Optional[list[str]] = None

    def _argparser(self) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser()

        parser.add_argument("--proj", "-p", type=str, default=None)
        parser.add_argument("--status", "-s", type=str, default=None)
        parser.add_argument(
            "--not-status", "-S", action="append", type=str, default=None
        )
        parser.add_argument("--user", "-u", type=str, default=None)
        parser.add_argument("--participant", "-P", action="store_true")
        parser.add_argument("--owner", "-O", action="store_true")
        parser.add_argument("args", nargs=argparse.REMAINDER)

        return parser

    @property
    def inc_status(self) -> list[str]:
        if self.status is None:
            return []
        result: list[str] = []
        for status in self.status:
            result.extend(status.split(","))
        return result

    @property
    def exc_status(self) -> list[str]:
        if self.not_status is None:
            return []
        result: list[str] = []
        for status in self.not_status:
            result.extend(status.split(","))
        return result

    def parse_args(self, argv: Iterable[str]) -> "Config":
        self._argparser().parse_args(argv, namespace=self)
        if self.args is None:
            self.args = []
        return self


# --------------------------------------------------------------------
class TaskService(Service):
    def __init__(self):
        super().__init__()
        self.commands = CommandMap(self)

    def _help_text(self) -> str:
        return (
            "`task [cmd]`\n  Task management system.  Type `task help` for more info."
        )

    def handles_function(self, fn_name: str) -> bool:
        return fn_name == "task"

    async def invoke(
        self, instance_id: str, ctx: Optional[ServiceCallContext] = None, respond=False
    ) -> str:
        rt_assert(ctx is not None, "Not authorized.")
        assert ctx is not None
        cmd = "set"
        argv = [*ctx.args]

        if argv and argv[0] in self.commands:
            cmd = argv.pop(0)

        rt_assert(
            await django_sync(self.assert_chain)(ctx, "task:all", f"task:{cmd}"),
            "Not authorized.",
        )

        handler = self.commands.get(cmd)
        return await django_sync(handler)(ctx, *argv)

    def cmd_help(self, ctx: ServiceCallContext, command: Optional[str] = None) -> str:
        """
        `task help [command]`

        Get help about the available task commands.  If `command` is not specified,
        all commands are printed with their usage lines.
        """
        return format_command_help(self.commands, command)

    def _get_user_project(
        self, ctx: ServiceCallContext, proj_code: Optional[str] = None
    ) -> Project:
        if proj_code is None:
            proj = Project.get_default_for_user(ctx.user)
            if proj is None:
                raise ValueError(
                    "No project code provided and no default defined for user."
                )
        else:
            proj = Project.objects.filter(code=proj_code).first()
            if proj is None:
                raise ValueError(f"Project `{proj_code}` not found.")

        return proj

    def cmd_list(self, ctx: ServiceCallContext, *argv: str) -> str:
        """
        `task list [-s status,status,...] [-S notstatus,notstatus,...] [-p <proj>]`
        List tasks within the given project or the user's default project.
        """
        sb = io.StringIO()
        config = Config().parse_args(argv)
        proj = self._get_user_project(ctx, config.proj)
        tasks = proj.tasks(config.inc_status, config.exc_status)

        for task in tasks:
            print("- " + str(task), file=sb)

        return sb.getvalue()

    def cmd_ls(self, ctx: ServiceCallContext, *argv: str) -> str:
        """
        `task ls [-s status,status,...] [-S notstatus,notstatus,...] [-p <proj>]`
        Alias to `task list`.

        List tasks within the given project or the user's default project.
        """

        return self.cmd_list(ctx, *argv)

    def cmd_add(self, ctx: ServiceCallContext, *argv: str) -> str:
        """
        `task add [-p <proj>] name...`
        Add a new task with the given name to a project or your default project.
        """
        config = Config().parse_args(argv)
        proj = self._get_user_project(ctx, config.proj)

        assert config.args is not None

        name = " ".join(config.args)

        if len(name.strip()) == 0:
            raise ValueError("A task name is required.")

        access = proj.user_access(ctx.user)
        if access is None or not access.is_participant:
            raise ValueError("User is not a participant in project `{proj.code}`.")

        task = Task(project=proj, name=name, status=INIT_STATUS, description="")
        task.save()
        task.update_status(ctx.user, START_STATUS)
        return str(task)

    def cmd_rm(self, ctx: ServiceCallContext, *argv: str) -> str:
        """
        `task rm <code>...`
        Delete one or more tasks.
        """

        config = Config().parse_args(argv)

        assert config.args is not None

        if len(config.args) < 1:
            raise ValueError("A task code is required.")

        with transaction.atomic():
            for task_id in config.args:
                task = Task.objects.get(quadcode=task_id)
                access = task.project.user_access(ctx.user)
                if access is None or not access.is_participant:
                    raise ValueError(
                        "User is not a participant in project `{task.project.code}` to which `{task_id}` belongs."
                    )
                task.delete()

        if len(config.args) == 1:
            return "Deleted 1 task."
        else:
            return f"Deleted {len(config.args)} tasks."

    def cmd_set(self, ctx: ServiceCallContext, *argv: str) -> str:
        """
        `task set <code> <status>`
        Set the status of the given task by code to a new status.
        """
        config = Config().parse_args(argv)

        if not config.args:
            raise ValueError("Task code or command is required.")
        code = config.args.pop(0).upper()

        if not config.args:
            raise ValueError("New task status is required.")
        status = config.args.pop(0).upper()

        task = Task.objects.filter(quadcode=code).first()
        if task is None:
            raise ValueError(f"No task with code `{code}` was found.")

        access = task.project.user_access(ctx.user)
        if access is None or not access.is_participant:
            raise ValueError(
                "User is not a participant in project `{task.project.code}`."
            )

        task.update_status(ctx.user, status)
        return str(task)

    def cmd_mv(self, ctx: ServiceCallContext, *argv: str) -> str:
        """
        `task mv <-p proj> <code>`
        Move one or more tasks to a new project.
        User must be an owner of both the source and destination project.
        """

        config = Config().parse_args(argv)

        assert config.args is not None

        if len(config.args) < 1:
            raise ValueError("One or more task codes are required.")

        if config.proj is None:
            raise ValueError("A destination project code is required.")

        new_proj = Project.objects.get(code=config.proj)
        new_proj_access = new_proj.user_access(ctx.user)
        if new_proj_access is None or not new_proj_access.is_owner:
            raise ValueError(
                f"User is not an owner of destination project `{new_proj.code}`."
            )

        with transaction.atomic():
            for task_id in config.args:
                task = Task.objects.get(quadcode=task_id)
                access = task.project.user_access(ctx.user)
                if access is None or not access.is_owner:
                    raise ValueError(
                        f"User is not an owner of source project `{task.project.code}` for task `{task.quadcode}`."
                    )
                task.project = new_proj
                task.save()

        if len(config.args) > 1:
            return f"{len(config.args)} tasks moved to project `{new_proj.code}`."
        return f"Task `{config.args[0]}` moved to project `{new_proj.code}`."

    def cmd_desc(self, ctx: ServiceCallContext, *argv: str) -> str:
        """
        `task desc <code> [desc...]`
        Read all lines of or add a line to the description of a task.
        """

        config = Config().parse_args(argv)

        assert config.args is not None

        if len(config.args) < 1:
            raise ValueError("A task code is required.")

        task = Task.objects.get(quadcode=config.args.pop(0))

        access = task.project.user_access(ctx.user)
        if access is None or not access.is_participant:
            raise ValueError(
                f"User is not a participant in project `{task.project.code}`."
            )

        if len(config.args) > 0:
            line = " ".join(config.args)
            task.description += line + "\n"
            task.save()
            return f"Wrote line to description for task `{task.quadcode}`."

        return task.description

    def cmd_set_access(self, ctx: ServiceCallContext, *argv: str) -> str:
        """
        `task set_access <-p proj> <-u username> [--owner/-O] [--participant/-P]`
        Grant a user access to the given project.

        This action can only be taken by a project owner and not for
        themselves.
        """

        config = Config().parse_args(argv)
        if config.proj is None:
            raise ValueError("A project code is required.")

        if config.user is None:
            raise ValueError("A user is required.")

        proj = Project.objects.get(code=config.proj)
        user = User.objects.get(username=config.user)
        old_access = proj.user_access(user)

        if user.username == ctx.user.username and not ctx.user.is_superuser:
            raise ValueError("Can't grant or revoke your own project access.")

        with transaction.atomic():
            if old_access is not None:
                old_access.delete()

            access = ProjectAccess(
                user=user,
                project=proj,
                is_participant=config.participant,
                is_owner=config.owner,
                is_default=old_access.is_default if old_access is not None else False,
            )
            access.save()

        result = f"User `{user.username}` granted access to project `{proj.code}`"

        if config.owner and config.participant:
            result += " as an owner and participant"
        elif config.owner:
            result += " as an owner"
        elif config.participant:
            result += " as a participant"
        result += "."
        return result

    def cmd_revoke_access(self, ctx: ServiceCallContext, *argv: str) -> str:
        """
        `task revoke_access <-p proj> <-u username>`
        Revoke a user's access to the given project.

        This action can only be taken by a project owner and not for
        themselves.
        """
        config = Config().parse_args(argv)
        if config.proj is None:
            raise ValueError("A project code is required.")

        if config.user is None:
            raise ValueError("A user is required.")

        proj = Project.objects.get(code=config.proj)
        user = User.objects.get(username=config.user)
        old_access = proj.user_access(user)

        if user.username == ctx.user.username and not ctx.user.is_superuser:
            raise ValueError("Can't grant or revoke your own project access.")

        if old_access is None:
            raise ValueError(
                "User `{user.username}` already has no access to project `{proj.code}`."
            )

        old_access.delete()
        return "User access revoked for `{user.username}` to project `{proj.code}`."

    def cmd_mkproj(self, ctx: ServiceCallContext, *argv: str) -> str:
        """
        `task mkproj <-p code> <name...>`
        Creates a new project with the given code and name.
        """
        config = Config().parse_args(argv)
        owner = ctx.user

        if config.proj is None:
            raise ValueError("A project code is required.")

        if config.user is not None:
            owner = User.objects.get(username=config.user)

        assert config.args is not None

        name = " ".join(config.args)
        if len(name.strip()) == 0:
            raise ValueError("A project name is required.")

        with transaction.atomic():
            proj = Project(code=config.proj, name=name)
            proj.save()

            access = ProjectAccess(
                project=proj,
                user=owner,
                is_owner=True,
                is_participant=True,
                is_default=False,
            )
            access.save()

        return f"Created project with code `{config.proj}` owned by `{owner.username}`."

    def cmd_lsproj(self, ctx: ServiceCallContext, *argv: str) -> str:
        """
        `task lsproj [-u user]`
        List your projects or the projects for the given user.
        """
        config = Config().parse_args(argv)
        user = ctx.user

        if config.user is not None:
            user = User.objects.get(username=config.user)

        sb = io.StringIO()
        projects = Project.get_all_for_user(user)
        for proj in sorted(projects, key=lambda p: p.code):
            print(f"- {proj}", file=sb)

        return sb.getvalue()

    def cmd_setproj(self, ctx: ServiceCallContext, *argv: str) -> str:
        """
        `task setproj -p <code> [-u <user>]`
        Set your or another user's default project.
        """

        config = Config().parse_args(argv)
        if config.proj is None:
            raise ValueError("A project code is required.")

        proj: Project = Project.objects.get(code=config.proj)
        user = ctx.user
        if config.user is not None:
            user = User.objects.get(username=config.user)

        proj.set_as_default_for_user(user)
        return f"Set `{proj.code}` as the default project for `{user.username}`."

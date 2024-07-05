# --------------------------------------------------------------------
# models.py
#
# Author: Lain Musgrove (lain.proliant@gmail.com)
# Date: Sunday June 30, 2024
# --------------------------------------------------------------------

from typing import Iterable, Optional

from django.contrib.auth.models import User
from django.db import models, transaction
from django.db.models import Q
from django.utils import timezone
from mememo.models import Setting, TimestampedModel, id_field, quadcode_field

# --------------------------------------------------------------------
DAY_SECONDS = 60 * 60 * 24


# --------------------------------------------------------------------
class Project(TimestampedModel):
    id = id_field()
    code = models.CharField(max_length=4, unique=True)
    name = models.TextField()

    def __str__(self) -> str:
        return f"`{self.code}` {self.name}"

    def tasks(
        self, inc_status: list[str] = [], exc_status: list[str] = []
    ) -> Iterable["Task"]:
        qs = Task.objects.filter(project__id=self.id)
        if len(inc_status) > 0:
            qs = qs.filter(status__in=inc_status)
        if len(exc_status) > 0:
            qs = qs.exclude(status__in=exc_status)
        return qs

    def user_access(self, user: User) -> Optional["ProjectAccess"]:
        return ProjectAccess.objects.filter(user=user, project=self).first()

    def set_as_default_for_user(self, user: User):
        access = self.user_access(user)
        if access is None:
            raise ValueError(
                f"`{user.username}` does not have access to project `{self.code}`."
            )
        Project.clear_defaults_for_user(user)
        access.is_default = True
        access.save()

    @classmethod
    def get_all_for_user(cls, user: User) -> Iterable["Project"]:
        for access in ProjectAccess.objects.filter(user=user, is_participant=True):
            yield access.project

    @classmethod
    def get_default_for_user(cls, user: User) -> Optional["Project"]:
        access = ProjectAccess.objects.filter(user=user, is_default=True).first()
        if access:
            return access.project
        return None

    @classmethod
    def clear_defaults_for_user(cls, user: User):
        ProjectAccess.objects.filter(user=user).update(is_default=False)


# --------------------------------------------------------------------
class Task(TimestampedModel):
    id = id_field()
    quadcode = quadcode_field()
    name = models.TextField()
    description = models.TextField()
    status = models.TextField()
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    priority = models.FloatField(default=0.0)
    due_date = models.DateTimeField(null=True)

    def __str__(self) -> str:
        return f"`{self.created_at.date().isoformat()} {self.quadcode}` *{self.status}* {self.name}"

    def relative_priority(self) -> float:
        now = datetime.now()

        if self.due_date is None:
            return float(self.priority)

        elif self.due_date < now:
            past_due_priority = Setting.get("TODO_PAST_DUE_PRIORITY", "10", int)
            past_due_factor = Setting.get("TODO_PAST_DUE_FACTOR", "10", int)
            return float((self.priority + past_due_priority) * past_due_factor)

        else:
            soon_due_priority = Setting.get("TODO_SOON_DUE_PRIORITY", "10", int)
            soon_due_threshold_days = Settings.get(
                "TODO_SOON_DUE_THRESHOLD_DAYS", "5", int
            )
            due_in_days = (self.due_date - now).total_seconds() / DAY_SECONDS
            soon_due_priority_ratio = due_in_days / soon_due_threshold_days
            return float(self.priority + (soon_due_priority * soon_due_priority_ratio))

    def get_user_tasks(self, user: User) -> Iterable["Task"]:
        user_active_project_ids = set(
            proj.id for proj in Project.get_all_for_user(user)
        )
        task_ids: set[str] = set()

        for update in TaskUpdate.objects.filter(agent=user):
            if update.task.project.id in user_active_project_ids:
                if update.task.id not in task_ids:
                    yield update.task
                    task_ids.add(update.task.id)

    def update_status(self, user: User, status: str):
        with transaction.atomic():
            update = TaskUpdate(
                task=self,
                old_status=self.status,
                new_status=status,
                agent=user,
                agent_name=user.username,
            )
            self.status = status
            self.save()
            update.save()


# --------------------------------------------------------------------
class ProjectAccess(TimestampedModel):
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    is_owner = models.BooleanField(default=False)
    is_participant = models.BooleanField(default=False)
    is_default = models.BooleanField(False)

    def __str__(self) -> str:
        return f"{self.user.username} @ `{self.project.code}`"

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["project", "user"], name="unique_project_user"
            )
        ]


# --------------------------------------------------------------------
class TaskUpdate(TimestampedModel):
    task = models.ForeignKey(Task, on_delete=models.CASCADE)
    old_status = models.TextField()
    new_status = models.TextField()
    agent = models.ForeignKey(User, on_delete=models.DO_NOTHING)
    agent_name = models.TextField()

    def __str__(self) -> str:
        return f"{self.task.quadcode} {self.created_at}: {self.agent_name} set {old_status} -> {new_status}"

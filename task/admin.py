from django.contrib import admin

from task.models import Project, Task, ProjectAccess, TaskUpdate

admin.site.register(Project)
admin.site.register(Task)
admin.site.register(ProjectAccess)
admin.site.register(TaskUpdate)

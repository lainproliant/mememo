#!/usr/bin/env python
# --------------------------------------------------------------------
# build.py
#
# Author: Lain Musgrove (lain.musgrove@hearst.com)
# Date: Saturday October 7, 2023
# --------------------------------------------------------------------

from xeno.build import provide, task, build
from xeno.recipe import Recipe
from xeno.recipes.shell import sh
from xeno.shell import check

import subprocess


# --------------------------------------------------------------------
class BuildDockerImage(Recipe):
    def __init__(self, image_name, path):
        super().__init__()
        self.image_name = image_name
        self.path = path

    def done(self):
        try:
            check(["docker", "inspect", self.image_name], stderr=subprocess.DEVNULL)
            return True
        except Exception:
            return False

    async def clean(self):
        if self.done():
            check(["docker", "image", "rm", "-f", self.image_name])

    async def make(self):
        return sh(
            "docker buildx build -t {image_name} {path}",
            image_name=self.image_name,
            path=self.path,
        )

    def result(self):
        return self.image_name


# --------------------------------------------------------------------
@provide
def git_revision():
    return check("git log -1 --pretty=format:%h")


# --------------------------------------------------------------------
@provide
def image_name(git_revision):
    return f"mememo:{git_revision}"


# --------------------------------------------------------------------
@task
def docker_build(image_name):
    return BuildDockerImage(image_name, ".")


# --------------------------------------------------------------------
@task
def debug_run(docker_build):
    return sh("docker run -it {docker_build}", docker_build=docker_build, interact=True)


# --------------------------------------------------------------------
@task(default=True, dep="docker_build")
def docker_compose_run(docker_build):
    return sh("docker-compose up", env={"MEMEMO_IMAGE_NAME": docker_build.result()})


# --------------------------------------------------------------------
build()

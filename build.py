#!/usr/bin/env python
# --------------------------------------------------------------------
# build.py
#
# Author: Lain Musgrove (lain.musgrove@hearst.com)
# Date: Saturday October 7, 2023
# --------------------------------------------------------------------

import getpass

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
@task(keep=True)
def runtime_path():
    return sh(
        "mkdir -p {target} && chown -R {user} {target}",
        as_user="root",
        target="/opt/mememo",
        user=getpass.getuser(),
    )


# --------------------------------------------------------------------
@task(keep=True, dep="runtime_path")
def runtime_config(runtime_path):
    return sh(
        'read -p "Please write configuration file to {target}, then press Enter." && [ -f {target} ]',
        target="/opt/mememo/config.yaml",
        interact=True,
    )


# --------------------------------------------------------------------
@task(keep=True, dep="runtime_config")
def database(runtime_config):
    return sh(
        " ".join(
            [
                "pipenv run python manage.py migrate &&"
                "[ -f {target} ] &&"
                "pipenv run python manage.py createsuperuser"
            ]
        ),
        interact=True,
        target="/opt/mememo/db.sqlite3",
    )


# --------------------------------------------------------------------
@task
def migrate():
    return sh("pipenv run python manage.py migrate")


# --------------------------------------------------------------------
@task(dep="database")
def debug(database, docker_build):
    return sh(
        "docker run -it -p 8510:8510 -v /opt/mememo:/opt/mememo {docker_build}",
        docker_build=docker_build,
        interact=True,
        ctrlc=True,
    )


# --------------------------------------------------------------------
@task(default=True, dep="docker_build,database")
def up(docker_build, database):
    return sh(
        "docker-compose up --remove-orphans -d",
        env={"MEMEMO_IMAGE_NAME": docker_build.result()},
    )


# --------------------------------------------------------------------
@task(dep="docker_build")
def down(docker_build):
    return sh("docker-compose down", env={"MEMEMO_IMAGE_NAME": docker_build.result()})


# --------------------------------------------------------------------
@task(dep="up")
def watch(up, argv):
    image_name = "agent"

    if len(argv) > 0:
        image_name = argv[0]

    return sh(
        "docker attach --sig-proxy=false mememo-{image_name}",
        image_name=image_name,
        interact=True,
        ctrlc=True,
    )


# --------------------------------------------------------------------
@task(dep="up")
def talk(up):
    return sh("pipenv run bivalve -H localhost -p 8510", interact=True, ctrlc=True)


# --------------------------------------------------------------------
build()

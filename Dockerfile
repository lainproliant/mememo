FROM archlinux:latest
LABEL maintainer="lainproliant.com"

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

RUN pacman --noconfirm -Sy python python-pipenv
RUN useradd -ms /bin/bash mememo
USER mememo
WORKDIR /home/mememo
COPY . /home/mememo

RUN pipenv install

EXPOSE 8510

# During debugging, this entry point will be overridden. For more information, please refer to https://aka.ms/vscode-docker-python-debug
CMD ["pipenv", "run", "python", "manage.py", "runagent"]

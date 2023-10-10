FROM archlinux:latest
LABEL maintainer="lainproliant.com"

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

RUN pacman --noconfirm -Sy python python-pipenv firefox
RUN useradd -ms /bin/bash mememo
USER mememo
WORKDIR /home/mememo
COPY . /home/mememo

RUN pipenv install

EXPOSE 8510
EXPOSE 8080

CMD ["pipenv", "run", "python", "manage.py", "runagent"]

FROM archlinux:latest
LABEL maintainer="lainproliant.com"

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Create the `build` and `mememo` users.
RUN useradd -ms /bin/bash mememo
RUN useradd --no-create-home --shell=/bin/false build && usermod -L build
RUN echo "build ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers

# Setup the `/opt/mememo` volume.
RUN mkdir /opt/mememo
RUN chown mememo:mememo /opt/mememo
VOLUME /opt/mememo

# Install base dependencies.
RUN pacman --noconfirm -Syu git python python-pipenv pyenv base-devel geckodriver firefox

# Install Firefox ESR from the AUR as `build`.
#USER build
#WORKDIR /tmp
#RUN git clone https://aur.archlinux.org/firefox-esr-bin.git firefox && cd firefox && makepkg -si --noconfirm

# Copy the application and run `pipenv install` as `mememo`.
USER mememo
WORKDIR /home/mememo
COPY . /home/mememo
RUN pipenv install

# Expose the Bivalve (8510) and Django Admin (8080) ports.
EXPOSE 8510
EXPOSE 8080

# Run the agent.
CMD ["pipenv", "run", "python", "manage.py", "runagent"]

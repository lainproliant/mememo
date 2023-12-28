# --------------------------------------------------------------------
# agent.py
#
# Author: Lain Musgrove (lain.proliant@gmail.com)
# Date: Wednesday September 13, 2023
# --------------------------------------------------------------------

import io
import shlex
import secrets
from typing import Optional

from bivalve.agent import BivalveAgent
from bivalve.aio import Connection
from bivalve.logging import LogManager
from django.contrib.auth.models import Permission, User
from django.utils import timezone

from mememo.auth import (
    Session,
    admin,
    auth,
    authenticate,
    authorize_call,
    create_auth3p,
)
from mememo.config import Config
from mememo.constants import Permissions
from mememo.models import (
    AuthToken,
    ServiceGrant,
    ServiceGrantAssignment,
    ThirdPartyAuthentication,
    new_auth_token
)
from mememo.service import ServiceCallContext, ServiceManager
from mememo.util import django_sync, format_command_help

# --------------------------------------------------------------------
log = LogManager().get(__name__)


# --------------------------------------------------------------------
class MememoAgent(BivalveAgent):
    def __init__(self, service_manager: ServiceManager, host, port):
        super().__init__()
        self.sessions: dict[Connection.ID, Session] = {}
        self.host = host
        self.port = port
        self.service_manager = service_manager

    async def run(self):
        try:
            await self.serve(host=self.host, port=self.port)
            self.schedule(self.maintain_services())
        except Exception:
            log.exception("Failed to start server.")
            self.shutdown()

        await super().run()

    def on_connect(self, conn: Connection):
        self.sessions[conn.id] = Session(conn)

    def on_client_disconnect(self, conn: Connection):
        del self.sessions[conn.id]

    async def maintain_services(self):
        await self.service_manager.scheduled_update()
        self.schedule(self.maintain_services())

    async def fn_auth(
        self, conn: Connection, username_or_token: str, password: Optional[str] = None
    ):
        """
        `auth (<token>) | (<username> <password>)`

        Authenticate this session using the given credentials.

        Allowed: Everyone.
        """

        session = self.sessions[conn.id]

        if password is None:
            plaintext_token = username_or_token
            user = await django_sync(AuthToken.resolve)(plaintext_token)
            if user is None:
                raise RuntimeError("Invalid auth token.")
            session.user = user

        else:
            username = username_or_token
            session.user = await authenticate(username=username, password=password)
            if session.user is None:
                raise RuntimeError("Invalid credentials.")

        return f"Authenticated as `{session.user.username}`.\n"

    @auth
    async def fn_help(
        self, conn: Connection, user: User, command: Optional[str] = None
    ):
        """
        `help [command]`

        Get help about the available agent functions.  If `command` is not specified,
        all commands are printed with their usage lines.
        """

        return format_command_help(self._functions, command)

    @django_sync
    def fn_auth3p(
        self,
        conn: Connection,
        identity: str,
        alias: str,
        challenge: Optional[str] = None,
    ):
        """
        `auth3p <identity> <alias> [challenge]`

        Authenticate a third-party user.

        If `challenge` is not provided, a secret challenge code is generated
        which needs to be provided by the same user again to authenticate them.
        This code can be listed out by gatekeepers with the `lsauth3p` function.

        Allowed: Non-superuser users with `mememo.third-party-gateway` sys permissions.
        """

        session = self.sessions[conn.id]

        if session.user is None or not session.user.has_perm(
            Permissions.THIRD_PARTY_GATEWAY
        ):
            raise RuntimeError(
                "Can't authenticate third-party users, this user is not a third party gateway."
            )

        if challenge is None:
            auth3p = create_auth3p(identity, alias)

            return "Ask the administrator for a challenge code, then send it back to me via `auth <challenge-code>`."

        else:
            auth3p = ThirdPartyAuthentication.objects.filter(identity=identity).first()
            if auth3p is None:
                raise RuntimeError("Not permitted.")

        now = timezone.now()

        if now > auth3p.expiry_dt:
            auth3p.delete()
            raise RuntimeError("Challenge has expired.")

        if challenge != auth3p.challenge:
            auth3p.delete()
            raise RuntimeError("Challenge failed.")

        user = User.objects.filter(username=auth3p.alias).first()
        if user is None:
            user = User.objects.create(username=auth3p.alias)
            user.set_password(secrets.token_urlsafe(128))
            user.save()

        auth3p.user = user
        auth3p.challenge = ""
        auth3p.expiry_dt = now + Config.get().auth3p.get_expiry()
        auth3p.save()
        return f"You're authenticated, @<{user.username}>.  Your authorization will expire on {auth3p.expiry_dt.isoformat()}.\n"

    @auth(Permissions.GATEKEEPER)
    def fn_user(
        self,
        conn: Connection,
        user: User,
        mode: str,
        username: str,
        passwd: Optional[str] = None,
    ):
        """
        `user <add|rm> <username> [password]`

        Add or remove Mememo user accounts.

        Allowed: Users with `mememo.gatekeeper` sys permissions.
        Not Allowed: Superusers can't be removed except by other superusers.
        """

        match mode:
            case "add":
                user = User.objects.create(username=username)
                if passwd is not None:
                    user.set_password(passwd)
                    user.save()
                    return f"Created new user `{user.username}`.\n"
                else:
                    passwd = new_auth_token()
                    user.set_password(passwd)
                    return (
                        f"Created new user `{user.username}` with password `{passwd}`.\n"
                    )

            case "rm":
                user = User.objects.get(username=username)
                if user.is_superuser and not user.is_superuser:
                    raise RuntimeError(
                        "Non-superusers are not allowed to remove superusers."
                    )
                user.delete()
                return f"Removed user `{user.username}`.\n"

            case _:
                raise ValueError(f"Invalid mode: `{mode}`")

    @auth
    def fn_hello(self, conn: Connection, user: User, *argv):
        """
        `hello`

        A simple hello response to determine if the user is properly
        authenticated.

        Allowed: any authenticated user
        """
        return f"Hello, @<{user.username}>!\n"

    @auth(Permissions.GATEKEEPER)
    def fn_lsauth3p(self, conn: Connection, user: User, username: Optional[str] = None):
        """
        `lsauth3p [username]`

        List pending third-party authentication requests.

        If `username` is provided, only third-party authentication requests
        for the givevn user are provided.

        Allowed: Users with `mememo.gatekeeper` sys permissions.
        """

        results = []
        auth3p_filter = ThirdPartyAuthentication.objects.all().exclude(
            challenge__exact=""
        )
        if username is not None:
            auth3p_filter = auth3p_filter.filter(alias=username)

        for auth3p in auth3p_filter:
            results.append(f"{auth3p.identity} ({auth3p.alias}): {auth3p.challenge}")
        sb = io.StringIO()
        print("```", file=sb)
        for result in results:
            print(result, file=sb)
        print("```", file=sb)
        return sb.getvalue()

    @auth(Permissions.GATEKEEPER)
    def fn_grant(
        self,
        conn: Connection,
        user: User,
        username: str,
        mode: str,
        grant_code: Optional[str] = None,
    ):
        """
        `grant <username> <add|rm|purge> <service_name>:<grant_name>`

        Add, remove, or purge user service grants.

        Allowed: Users with `mememo.gatekeeper` sys permissions.
        """

        user = User.objects.get(username=username)

        match mode:
            case "add":
                grant = ServiceGrant.by_code(grant_code)
                assignment = ServiceGrantAssignment(user=user, grant=grant)
                assignment.save()
                return f"Service grant `{grant.to_code()}` added to `{user.username}`.\n"

            case "rm":
                grant = ServiceGrant.by_code(grant_code)
                assignment = ServiceGrantAssignment.objects.get(user=user, grant=grant)
                assignment.delete()
                return (
                    f"Service grant `{grant.to_code()}` removed from `{user.username}`."
                )

            case "purge":
                ServiceGrantAssignment.objects.filter(user=user).delete()
                return f"Removed all service grants from `{user.username}`.\n"

            case _:
                raise ValueError(f"Invalid mode: `{mode}`")

        assignment = ServiceGrantAssignment(user=user, grant=grant)
        assignment.save()

    @admin
    def fn_auth3p_override(self, conn: Connection, user: User, identity: str):
        """
        `auth3p_override <identity>`

        Forcefully approves or refreshes a third-party authentication request.

        Allowed: Superusers only.
        """

        now = timezone.now()
        auth3p = ThirdPartyAuthentication.objects.filter(identity=identity).first()
        if not auth3p:
            raise RuntimeError("No third party auth request exists for this identity.")
        user = User.objects.filter(username=auth3p.alias).first()
        if user is None:
            user = User.objects.create(username=auth3p.alias)
            user.set_password(secrets.token_urlsafe(128))
            user.save()

        auth3p.user = user
        auth3p.challenge = ""
        auth3p.expiry_dt = now + Config.get().auth3p.get_expiry()
        auth3p.save()
        return f"Third party auth override successful for @<{user.username}>.  Their authorization will expire on {auth3p.expiry_dt.isoformat()}.\n"

    @admin
    def fn_lsgrant(self, conn: Connection, user: User, username: Optional[str] = None):
        """
        `lsgrant [username]`

        List all grants, or all grants assigned to a user.

        Allowed: Superusers only.
        """

        results = []
        if username is None:
            for grant in ServiceGrant.objects.all():
                results.append(grant.to_code())
        else:
            for grant in ServiceGrant.by_user(User.objects.get(username=username)):
                results.append(grant)
        sb = io.StringIO()
        print("```", file=sb)
        for result in results:
            print(result, file=sb)
        print("```", file=sb)
        return sb.getvalue()

    @admin
    def fn_lspermit(self, conn: Connection, user: User):
        """
        `lspermit`

        List all sys permissions.

        Allowed: Superusers only.
        """

        results = []
        for perm in Permission.objects.all():
            results.append(f"{perm.codename}")
        sb = io.StringIO()
        print("```", file=sb)
        for result in results:
            print(result, file=sb)
        print("```", file=sb)
        return sb.getvalue()

    @admin
    def fn_lsuser(self, conn: Connection, user: User):
        """
        `lsuser`

        List all Mememo user accounts.

        Allowed: Superusers only.
        """

        results = []
        for user in User.objects.all():
            results.append(user.username)
        sb = io.StringIO()
        print("```", file=sb)
        for result in results:
            print(result, file=sb)
        print("```", file=sb)
        return sb.getvalue()

    @admin
    def fn_mktoken(self, conn: Connection, user: User, username: str):
        """
        `mktoken <username>`

        Makes an auth token for the given user or replaces an existing one.
        The old token is blown away and can no longer be used.

        Allowed: Superusers only.
        """

        sb = io.StringIO()
        user = User.objects.get(username=username)
        user_token = AuthToken.objects.filter(user=user).first()
        if user_token is not None:
            user_token.delete()
        plaintext_token, new_token = AuthToken.new(user)

        print(f"Generated a new auth token for `{user.username}`.", file=sb)
        print("```", file=sb)
        print(plaintext_token, file=sb)
        print("```", file=sb)

        return sb.getvalue()

    @admin
    def fn_rmtoken(self, conn: Connection, user: User, username: str):
        """
        `rmtoken <username>`

        Removes the auth token for the given user.

        Allowed: Superusers only.
        """

        user = User.objects.get(username=username)
        user_token = AuthToken.objects.get(user=user)
        user_token.delete()
        return f"Deleted auth token for `{user.username}`.\n"

    @admin
    def fn_mkgrant(self, conn: Connection, user: User, grant_code: str):
        """
        `mkgrant <service_name>:<grant_name>`

        Creates a new service grant with the given name.

        Allowed: Superusers only.
        """

        service_name, grant_name = ServiceGrant.split(grant_code)
        grant = ServiceGrant(service_name=service_name, grant_name=grant_name)
        grant.save()
        return f"Created service grant `{grant.to_code()}`.\n"

    @admin
    def fn_passwd(
        self, conn: Connection, user: User, username: str, passwdA: str, passwdB: str
    ):
        """
        `passwd <username> <passwd> <passwd>`

        Set the user's password to the given raw password.

        Allowed: Superusers only.
        """

        user = User.objects.get(username=username)
        if passwdA != passwdB:
            raise ValueError("Passwords do not match.")
        user.set_password(passwdA)
        user.save()

        return f"Password for user `{username}` has been changed.\n"

    @admin
    def fn_permit(
        self, conn: Connection, user: User, username: str, mode: str, perm: str
    ):
        """
        `permit <username> <add|rm> <perm>`

        Add or remove the given permission from the given user account.

        Allowed: Superusers only.
        """

        user = User.objects.get(username=username)
        permission = Permission.objects.get(codename=perm)

        match mode:
            case "add":
                user.user_permissions.add(permission)
                user.save()
                return f"System permission `{perm}` added for user `{username}`.\n"
            case "rm":
                user.user_permissions.remove(permission)
                user.save()
                return f"System permission `{perm}` removed for user `{username}`.\n"
            case _:
                raise ValueError(f"Invalid mode: `{mode}`")

    async def on_unrecognized_function(self, conn: Connection, *argv):
        session = self.sessions[conn.id]
        fn_name, *real_argv = argv
        message = shlex.join(argv)
        user, fn_argv = await django_sync(authorize_call)(session.user, [], *real_argv)

        ctx = ServiceCallContext(user, fn_name, [*fn_argv])

        if self.service_manager.has_message_handler(message):
            service = self.service_manager.get_message_handler(message)
        else:
            service = self.service_manager.get_function_handler(fn_name)

        try:
            await service.prepare(self.service_manager.instance_id, ctx)
            return await service.invoke(self.service_manager.instance_id, ctx)

        except Exception as e:
            log.exception("Failed to invoke service handler.")
            raise e

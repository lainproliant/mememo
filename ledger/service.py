# --------------------------------------------------------------------
# service.py
#
# Author: Lain Musgrove (lain.proliant@gmail.com)
# Date: Thursday November 2, 2023
# --------------------------------------------------------------------

import io
import locale
import re
import shlex
from decimal import Decimal
from typing import Optional

import tabulate
from bivalve.util import Commands as CommandMap
from django.contrib.auth.models import User
from mememo.service import Service, ServiceCallContext
from mememo.util import django_sync, format_command_help, rt_assert
from price_parser import Price

from ledger.models import Account, AccountAccess, Transaction

# --------------------------------------------------------------------
TABLE_WIDTH = 70
RX_MONEY = r"\$\d+(,?\d{3})*(\.\d{2})?"
DATE_FORMAT = "%Y-%m-%d %H:%M"
SIGILS = ["!cash", "!$"]


# --------------------------------------------------------------------
def parse_money(s: str) -> Decimal:
    price = Price.fromstring(s)
    if price is None or price.amount is None:
        raise ValueError("Could not parse monetary value.")
    return price.amount


# --------------------------------------------------------------------
def format_money(value: Decimal) -> str:
    return locale.currency(value)


# --------------------------------------------------------------------
def make_transaction_report(txns: list[Transaction]) -> str:
    sb = io.StringIO()

    tab_data = []
    if txns:
        for txn in txns:
            tab_data.append(
                [
                    txn.created_at.strftime(DATE_FORMAT),
                    txn.agent.username if txn.agent else "None",
                    format_money(txn.amount),
                    txn.from_account.name if txn.from_account else "None",
                    txn.to_account.name if txn.to_account else "None",
                    txn.note if txn.note else "None",
                ]
            )

        content = tabulate.tabulate(
            tab_data, headers=("Time", "Agent", "Amount", "From", "To", "Note")
        )
    else:
        content = "No transactions were found."

    print("```", file=sb)
    print(content, file=sb)
    print("```", file=sb)
    return sb.getvalue()


# --------------------------------------------------------------------
def make_balance_report(accounts: list[Account]) -> str:
    sb = io.StringIO()
    tab_data = []

    if accounts:
        for account in accounts:
            tab_data.append([account.name, format_money(account.balance())])
        content = tabulate.tabulate(tab_data, headers=("Account", "Balance"))
    else:
        content = "No accounts were found."

    print("```", file=sb)
    print(content, file=sb)
    print("```", file=sb)
    return sb.getvalue()


# --------------------------------------------------------------------
def txn_result(txn: Transaction, account: Account) -> str:
    sb = io.StringIO()

    print(make_transaction_report([txn]), file=sb)
    print(make_balance_report([account]), file=sb)
    return sb.getvalue()


# --------------------------------------------------------------------
class LedgerService(Service):
    def __init__(self):
        super().__init__()
        self.commands = CommandMap(self)

    def handles_function(self, fn_name: str) -> bool:
        return fn_name == "cash" or fn_name in SIGILS

    def handles_message(self, message: str) -> bool:
        argv = shlex.split(message)
        if len(argv) < 1:
            return False
        return any(sigil == argv[0] for sigil in SIGILS)

    async def invoke(
        self, instance_id: str, ctx: Optional[ServiceCallContext] = None
    ) -> str:
        rt_assert(ctx is not None, "Not authorized.")
        assert ctx
        cmd = "summary"
        argv = [*ctx.args]

        if argv and self.commands.has(argv[0]):
            cmd = argv.pop(0)

        rt_assert(
            self.assert_grants(ctx, "ledger:all")
            or self.assert_grants(ctx, f"ledger:{cmd}"),
            "Not authorized.",
        )
        handler = self.commands.get(cmd)
        return await django_sync(handler)(ctx, *argv)

    def cmd_help(self, ctx: ServiceCallContext, command: Optional[str] = None) -> str:
        """
        `cash help [command]`

        Get help about the available cash commands.  If `command` is not specified,
        all commands are printed with their usage lines.
        """
        return format_command_help(self.commands, command)

    def cmd_summary(self, ctx: ServiceCallContext, *account_names: str) -> str:
        """
        `cash summary [accounts]`

        Print the balances of the given accounts.  If `account_names` is not provided,
        balances for all accounts you have access to will be printed.

        Allowed: Users with `ledger:all` or `ledger:summary` grants.
        """

        accounts: list[Account] = []

        if account_names:
            for name in account_names:
                account = Account.objects.filter(name=name).first()
                rt_assert(
                    account is not None and account.has_access(ctx.user),
                    f"The account `{name}` does not exist or you don't have access to it.",
                )
                assert account
                accounts.append(account)

        else:
            accounts = [*Account.get_all_for_user(ctx.user)]

        rt_assert(len(accounts) > 0, "You don't have any accounts.")
        return make_balance_report(accounts)

    def cmd_setdefault(
        self, ctx: ServiceCallContext, account_name: str, username: Optional[str] = None
    ) -> str:
        """
        `cash setdefault <account_name> [username]`

        Set the default account for yourself or another user.

        Allowed: Users with `ledger:all` or `ledger:setdefault` grants.  Only users
                 with `ledger:others` may set default accounts for others.
        """
        account = Account.objects.filter(name=account_name).first()
        if account is None:
            raise ValueError("Account not found.")
        if username and username != ctx.user.username:
            user = User.objects.filter(username=username)
            account.set_as_default_for_user(user)
            rt_assert(
                self.assert_grants(ctx, "ledger:others"),
                "You aren't allowed to set the default account for other users.",
            )
            return f"Set `{account.name}` as the default account for `{username}`."
        account.set_as_default_for_user(ctx.user)
        return f"Set `{account.name}` as your default account."

    def cmd_rmdefault(self, ctx: ServiceCallContext) -> str:
        """
        `cash rmdefault`

        Make it so you no longer have a default account.

        Allowed: Users with `ledger:all` or `ledger:rmdefault` grants.
        """
        Account.clear_defaults_for_user(ctx.user)
        return "You no longer have a default account."

    def cmd_mkdefaultaccount(
        self,
        ctx: ServiceCallContext,
        account_name: str,
        owner_username: Optional[str] = None,
    ) -> str:
        """
        `cash mkdefaultaccount <account> [username]`

        Make an account and set it as the default for yourself or another user.

        Allowed: Users with `ledger:all` or `ledger:mkdefaultaccount` grants.
                 Only users with `ledger:others` may set default accounts
                 for others.
        """
        sb = io.StringIO()
        if owner_username is not None and owner_username != ctx.user.username:
            rt_assert(
                self.assert_grants(ctx, "ledger:others"),
                "You aren't allowed to set the default account for other users.",
            )
        print(self.cmd_mkaccount(ctx, account_name, owner_username), file=sb)
        print(self.cmd_setdefault(ctx, account_name, owner_username), file=sb)
        return sb.getvalue()

    def cmd_mkaccount(
        self,
        ctx: ServiceCallContext,
        account_name: str,
        owner_username: Optional[str] = None,
    ) -> str:
        """
        `cash mkaccount <account> [username]`

        Make an account.  If `username` is provided, that user will become
        the account owner, otherwise you are the owner.

        Allowed: Users with `ledger:all` or `ledger:mkaccount` grants.
        """
        rt_assert(
            re.match(r"^[\w]+$", account_name) is not None,
            "Account name must be a valid number or identifier with no spaces.",
        )
        if owner_username is not None:
            owner_user = User.objects.filter(username=owner_username).first()
            rt_assert(owner_user is not None, "Specified owner username not found.")
        else:
            owner_user = ctx.user
        account = Account(name=account_name)
        account.save()
        account_access = AccountAccess(user=owner_user, account=account, is_owner=True)
        account_access.save()
        return f"Created account `{account.name}` for `{account_access.user.username}`."

    def cmd_rmaccount(self, ctx: ServiceCallContext, account_name: str) -> str:
        """
        `cash rmaccount <account>`

        Remove an account.

        Allowed: Users with `ledger:all` or `ledger:setdefault` grants and who have
                 owner-level access to the given account.
        """
        account = Account.objects.filter(name=account_name).first()
        rt_assert(
            account.has_access(ctx.user, owner=True),
            "Only an account owner can delete this account.",
        )
        account.delete()
        return "Account has been deleted."

    def cmd_seed(
        self,
        ctx: ServiceCallContext,
        account_or_amount: str,
        amount_or_account: Optional[str] = None,
    ) -> str:
        """
        `cash seed (<amount>) | (<account> <amount>) | (<amount> <account>)`

        Seed the given account or your default account with an amount of money.
        Creates a transaction where the payout (from_account) is null, and the
        payin account is the given account.

        Allowed: Users with `ledger:all` or `ledger:seed` grants, and who have
                 access to the given account.
        """
        account_name = None
        try:
            amount = parse_money(account_or_amount)
            if amount_or_account is None:
                account = Account.get_default_for_user(ctx.user)
                account_name = account.name
            else:
                account = Account.objects.get(name=amount_or_account)
                account_name = amount_or_account
            rt_assert(
                account is not None,
                "You have no default account, so an account must be specified.",
            )

        except ValueError:
            rt_assert(amount_or_account is not None, "Missing amount for seed.")
            assert amount_or_account
            amount = parse_money(amount_or_account)
            account = Account.objects.filter(name=account_or_amount).first()
            account_name = account_or_amount

        rt_assert(
            account is not None and account.has_access(ctx.user),
            f"Account `{account_name}` not found or you don't have access..",
        )

        assert account
        txn = Transaction(
            agent=ctx.user,
            from_account=None,
            to_account=account,
            amount=amount,
            note="Seed amount",
        )
        txn.save()
        return txn_result(txn, account)

    def cmd_giveaccess(
        self, ctx: ServiceCallContext, account_name: str, username: str
    ) -> str:
        """
        `cash giveaccess <account> <username>`

        Give the given user access to the given account.

        Allowed: Users with `ledger:all` or `ledger:addaccess` grants, who have access
                 to the given account.
        """

        account = Account.objects.get(name=account_name)
        rt_assert(
            account.has_access(ctx.user), "You don't have access to this account."
        )
        user = User.objects.get(username=username)
        access = AccountAccess(user=user, account=account)
        access.save()
        return f"Access granted for user `{user.username}` to account `{account.name}`"

    def cmd_revokeaccess(
        self, ctx: ServiceCallContext, account_name: str, username: str
    ) -> str:
        """
        `cash revokeaccess <account> <username>`

        Remove the given user's access to the given account.

        Allowed: Users with `ledger:all` or `ledger:rmaccess` grants, who have access
                 to the given account.
        """
        account = Account.objects.get(name=account_name)
        rt_assert(
            account.has_access(ctx.user), "You don't have access to this account."
        )
        user = User.objects.get(username=username)
        access = AccountAccess.objects.get(user=user, account=account)
        access.delete()
        return f"Access revoked for user `{user.username}` to account `{account.name}`"

    def cmd_spend(self, ctx: ServiceCallContext, *args) -> str:
        """
        `cash spend (<amount>) | (<account> <amount>) [notes...]`

        Spend from the given account or your default account an amount of money.
        Creates a transaction where the payout (from_account) is the given account
        and the payin (to_account) account is null.  If a note is specified,
        it is provided with the transaction otherwise it is null.

        Allowed: Users with `ledger:all` or `ledger:spend` grants, and who have
                 access to the given account.
        """

        rt_assert(len(args) > 0, "No arguments provided.")
        argv = [*args]
        account_name = None
        try:
            amount = parse_money(argv[0])
        except ValueError:
            account_name = argv[0]
        argv.pop(0)

        if account_name is None:
            account = Account.get_default_for_user(ctx.user)
            rt_assert(
                account is not None,
                "No account specified and you have no default account set.",
            )
        else:
            account = Account.objects.filter(name=account_name)
            rt_assert(
                account is not None and account.has_access(ctx.user),
                "You don't have access to this account.",
            )
            amount = parse_money(argv[0])
            argv.pop(0)

        assert account is not None
        txn = Transaction(
            agent=ctx.user,
            from_account=None,
            to_account=account,
            amount=amount,
            note=shlex.join(argv),
        )
        txn.save()
        return txn_result(txn, account)

    def cmd_ledger(self, ctx: ServiceCallContext, *args: str):
        """
        `cash ledger ([account...] | [agent=<username>...] | [<lookback_days>])...`

        Print a report of transactions matching the given criteria.
        If no agent or account criteria are provided, transactions from your default
        account are reported.  If you don't have a default account, all transactions
        where you are the agent are reported.

        Allowed: Users with `ledger:all` or `ledger:ledger` grants, and who have access
                 to the given accounts.
        """
        account_names: list[str] = []
        agent_names: list[str] = []
        lookback_days = 30

        for arg in args:
            if arg.startswith("agent="):
                agent_names.append(arg.split("=")[1])
            elif re.match(r"\d+", arg):
                lookback_days = int(arg)
            else:
                account_names.append(arg)

        agents: list[User] = []
        accounts: list[Account] = []

        for name in agent_names:
            agents.append(User.objects.get(username=name))
        for name in account_names:
            account = Account.objects.get(name=name)
            rt_assert(
                account.has_access(ctx.user),
                f"You don't have access to the `{name}` account ledger.",
            )
            accounts.append(account)

        if not agents and not accounts:
            account = Account.get_default_for_user(ctx.user)
            if account:
                accounts.append(account)
            else:
                agents.append(ctx.user)

        return make_transaction_report(
            Transaction.filter(agents, accounts, lookback_days)
        )

    def cmd_pay(
        self,
        ctx: ServiceCallContext,
        from_account_name: str,
        to_account_name: str,
        amount_str: str,
        *args,
    ) -> str:
        """
        `cash pay <from_account> <to_account> <amount> [notes...]`

        Create a transaction, moving funds from one account to another.
        Notes are added to the transaction if provided.

        Allowed: Users with `ledger:all` or `ledger:pay` grants, and who
                 have access to the `from_account` specified.
        """
        from_account = Account.objects.filter(name=from_account_name).first()
        to_account = Account.objects.filter(name=to_account_name).first()
        rt_assert(from_account is not None, "Payout account not found.")
        rt_assert(to_account is not None, "Payin account not found.")
        assert from_account is not None and to_account is not None

        rt_assert(
            from_account.has_access(ctx.user),
            f"You don't have access to payout from the `{from_account.name}` account.",
        )

        amount = parse_money(amount_str)
        if len(args) == 0:
            note = None
        else:
            note = shlex.join(args)

        txn = Transaction(
            agent=ctx.user,
            from_account=from_account,
            to_account=to_account,
            amount=amount,
            note=note,
        )
        txn.save()
        return txn_result(txn, from_account)

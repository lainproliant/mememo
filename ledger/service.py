# --------------------------------------------------------------------
# service.py
#
# Author: Lain Musgrove (lain.proliant@gmail.com)
# Date: Thursday November 2, 2023
# --------------------------------------------------------------------

import re
import io
from decimal import Decimal
from typing import Optional

from bivalve.util import Commands as CommandMap
from mememo.service import Service, ServiceCallContext

from django.contrib.auth.models import User
from ledger.models import Account, Transaction
from mememo.util import rt_assert


# --------------------------------------------------------------------
class LedgerService(Service):
    SIGILS = ["!cash", "!$"]

    def __init__(self):
        super().__init__()
        self.commands = CommandMap(self)

    def handles_message(self, message: str) -> bool:
        return any(message.startswith(sigil) for sigil in self.SIGILS)

    def invoke(self, instance_id: str, ctx: Optional[ServiceCallContext] = None) -> str:
        rt_assert(ctx is not None, "Not authorized.")
        cmd = "TODO"

        assert f"ledger:{cmd}" in ctx.get_grants(), "Not authorized."

    def cmd_mkaccount(
        self,
        ctx: ServiceCallContext,
        account_name: str,
        owner_username: Optional[str] = None,
    ) -> str:
        rt_assert(
            re.match(r"^[\w]+$", account_name),
            "Account name must be a valid number or identifier with no spaces.",
        )
        if owner_username is not None:
            owner_user = User.objects.filter(username=owner_username).first()
            rt_assert(owner_user is not None, "Specified owner username not found.")
        else:
            owner_user = ctx.user
        account = Account(name=account_name, owner=owner_user)
        account.save()
        return "Created account `{account.name}` owned by `{account.owner.username}`."

    def cmd_rmaccount(self, ctx: ServiceCallContext, account_name: str) -> str:
        account = Account.objects.filter(name=account_name).first()
        rt_assert(
            account.owner == ctx.user,
            "Only the account owner can delete this account.",
        )
        account.delete()
        return "Account has been deleted."

    def cmd_seed(self, ctx: ServiceCallContext, account_name: str, amount_str: str) -> str:
        sb = io.StringIO()
        account = Account.objects.filter(name=account_name).first()
        rt_assert(account, "Account not found.")
        rt_assert(account.has_access(ctx.user), "Not authorized.")
        txn = Transaction(from_account=None, to_account=account, amount=Decimal(amount_str), note="Seed amount")
        txn.save()
        print(str(txn), file=sb)
        print(str(account), file=sb)
        return sb.getvalue()

    def cmd_pay(self, ctx: ServiceCallContext, *args) -> str:
        rt_assert(len(args) > 0, "No arguments provided.")

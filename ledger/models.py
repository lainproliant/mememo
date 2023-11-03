# --------------------------------------------------------------------
# models.py
#
# Author: Lain Musgrove (lain.proliant@gmail.com)
# Date: Thursday November 2, 2023
# --------------------------------------------------------------------

from decimal import Decimal
from django.utils import timezone
from datetime import timedelta

from django.contrib.auth.models import User
from django.db import models
from django.db.models import Q
from mememo.models import TimestampedModel, id_field
from typing import Optional, Iterable


# --------------------------------------------------------------------
class Account(TimestampedModel):
    id = id_field()
    name = models.TextField(unique=True)

    def balance(self) -> Decimal:
        from_total = Transaction.objects.filter(from_account=self).aggregate(
            total=models.Sum("amount")
        )["total"]
        to_total = Transaction.objects.filter(to_account=self).aggregate(
            total=models.Sum("amount")
        )["total"]
        to_total = to_total or 0
        from_total = from_total or 0
        return to_total - from_total

    def has_access(self, user: User, owner=False):
        if user.is_superuser:
            return True
        access = AccountAccess.objects.filter(user=user, account=self).first()
        if access is None:
            return False

        if owner and not access.is_owner:
            return False

        return True

    def set_as_default_for_user(self, user: User):
        access = AccountAccess.objects.get(user=user, account=self)
        Account.clear_defaults_for_user(user)
        access.is_default = True
        access.save()

    @classmethod
    def get_all_for_user(cls, user: User) -> Iterable["Account"]:
        for access in AccountAccess.objects.filter(user=user):
            yield access.account

    @classmethod
    def get_default_for_user(cls, user: User) -> Optional["Account"]:
        access = AccountAccess.objects.filter(user=user, is_default=True).first()
        if access:
            return access.account
        return None

    @classmethod
    def clear_defaults_for_user(cls, user: User):
        AccountAccess.objects.filter(user=user).update(is_default=False)


# --------------------------------------------------------------------
class AccountAccess(TimestampedModel):
    account = models.ForeignKey(Account, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    is_owner = models.BooleanField(default=False)
    is_default = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["account", "user"], name="unique_account_user"
            )
        ]


# --------------------------------------------------------------------
class Transaction(TimestampedModel):
    agent = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    from_account = models.ForeignKey(
        Account, on_delete=models.SET_NULL, null=True, related_name="payout"
    )
    to_account = models.ForeignKey(
        Account, on_delete=models.SET_NULL, null=True, related_name="payin"
    )
    note = models.TextField(null=True)

    @classmethod
    def filter(
        cls, agents: list[User] = [], accounts: list[Account] = [], lookback_days=30
    ) -> list["Transaction"]:
        qs = Transaction.objects.filter(
            created_at__gt=timezone.now() - timedelta(days=lookback_days)
        )

        if agents:
            qs = qs.filter(agent__in=agents)

        if accounts:
            qs = qs.filter(Q(from_account__in=accounts) | Q(to_account__in=accounts))

        return list(qs.order_by("-created_at"))

# --------------------------------------------------------------------
# models.py
#
# Author: Lain Musgrove (lain.proliant@gmail.com)
# Date: Thursday November 2, 2023
# --------------------------------------------------------------------

from decimal import Decimal

from django.contrib.auth.models import User
from django.db import models
from mememo.models import TimestampedModel, id_field


# --------------------------------------------------------------------
class Account(TimestampedModel):
    id = id_field()
    name = models.TextField()
    owner = models.ForeignKey(User, on_delete=models.CASCADE)

    def balance(self) -> Decimal:
        from_total = Transaction.objects.filter(from_account=self).aggregate(
            total=models.Sum("amount")
        )["total"]
        to_total = Transaction.objects.filter(to_account=self).aggregate(
            total=models.Sum("amount")
        )["total"]
        return to_total - from_total

    def has_access(self, user: User):
        return (
            user == self.owner
            or AccountAccess.objects.filter(user=user, account=self).first() is not None
        )


# --------------------------------------------------------------------
class AccountAccess(TimestampedModel):
    account = models.ForeignKey(Account, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)


# --------------------------------------------------------------------
class Transaction(TimestampedModel):
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    from_account = models.ForeignKey(
        Account, on_delete=models.SET_NULL, null=True, related_name="payout"
    )
    to_account = models.ForeignKey(
        Account, on_delete=models.SET_NULL, null=True, related_name="payin"
    )
    note = models.TextField()

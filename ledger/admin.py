from django.contrib import admin

from ledger.models import Account, AccountAccess, Transaction

admin.site.register(Account)
admin.site.register(AccountAccess)
admin.site.register(Transaction)

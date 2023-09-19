from django.contrib import admin

from mememo.models import Topic, Subscription, ThirdPartyAuthentication

# Register your models here.
admin.site.register(Topic)
admin.site.register(Subscription)
admin.site.register(ThirdPartyAuthentication)

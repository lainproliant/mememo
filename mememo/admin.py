from django.contrib import admin

from mememo.models import Topic, Subscription, ThirdPartyAuthentication, ServiceGrant, ServiceGrantAssignment

# Register your models here.
admin.site.register(Topic)
admin.site.register(Subscription)
admin.site.register(ThirdPartyAuthentication)
admin.site.register(ServiceGrant)
admin.site.register(ServiceGrantAssignment)

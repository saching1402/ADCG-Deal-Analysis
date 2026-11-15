from django.urls import path

from .views import AuditList

urlpatterns = [path('', AuditList.as_view())]

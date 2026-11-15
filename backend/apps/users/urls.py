from django.urls import path

from . import views

urlpatterns = [
    path('', views.UserList.as_view()),
    path('me/', views.MeView.as_view(), name='me'),
    path('me/password/', views.PasswordView.as_view()),
    path('<uuid:pk>/', views.UserDetail.as_view()),
    path('<uuid:pk>/reset-password/', views.UserResetPassword.as_view()),
]

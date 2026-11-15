from django.urls import path

from . import views

urlpatterns = [
    path('<uuid:pk>/comments/', views.DealComments.as_view()),
    path('<uuid:pk>/comments/<int:cid>/', views.DealCommentDetail.as_view()),
    path('<uuid:pk>/revise/', views.DealRevise.as_view()),
    path('', views.DealList.as_view()),
    path('stats/', views.PipelineStats.as_view()),
    path('suggest/', views.CompanySuggest.as_view()),
    path('<uuid:pk>/', views.DealDetail.as_view()),
    path('<uuid:pk>/files/', views.DealFiles.as_view()),
    path('<uuid:pk>/files/<int:fid>/', views.DealFileDetail.as_view()),
    path('<uuid:pk>/files/<int:fid>/replace/', views.DealFileReplace.as_view()),
    path('<uuid:pk>/analyze/', views.DealAnalyze.as_view()),
    path('<uuid:pk>/cancel/', views.DealCancel.as_view()),
    path('<uuid:pk>/memo/', views.DealMemo.as_view()),
    path('<uuid:pk>/free-space/', views.DealFreeSpace.as_view()),
]

from django.urls import path

from . import framework_views as v

urlpatterns = [
    path('', v.FrameworkList.as_view()),
    path('proposals/', v.ProposalList.as_view()),
    path('proposals/<int:pid>/', v.ProposalDecide.as_view()),
    path('<str:key>/', v.FrameworkDetail.as_view()),
    path('<str:key>/history/', v.FrameworkHistory.as_view()),
    path('<str:key>/restore/', v.FrameworkRestore.as_view()),
    path('<str:key>/reset-mine/', v.FrameworkResetMine.as_view()),
    path('<str:key>/propose/', v.FrameworkPropose.as_view()),
]

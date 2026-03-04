"""
URL configuration for football_api_project project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path
from football import views
from django.shortcuts import redirect

urlpatterns = [
    path("admin/", admin.site.urls),

    path("api/teams/", views.teams_collection),
    path("api/teams/<int:team_id>/", views.team_item),

    path("api/matches/", views.matches_collection),

    path("api/analytics/table/", views.league_table),

    path("api/analytics/performance/", views.performance_summary),

    path("api/analytics/win-probability/", views.win_probability),

    path("api/analytics/win-probability/batch/", views.win_probability_batch),

    path("api/analytics/predict-table/", views.predict_table),

    path("", lambda request: redirect("/dashboard/")),
    path("dashboard/", views.dashboard),
]

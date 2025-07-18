from django.urls import path
from . import views
# This should contain urls related to Pages ONLY

urlpatterns = [
    path('', views.pages_home, name='pages_home'),
    path('apps/', views.pages_apps, name='pages_apps'),
    path('partners/', views.pages_partners, name='pages_partners'),
]
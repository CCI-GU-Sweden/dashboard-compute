from django.urls import path
from .views import home

urlpatterns = [path("compute/", home, name="compute_home")]

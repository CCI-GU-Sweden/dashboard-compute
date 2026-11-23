from django.urls import path
from .views import home, day_detail

urlpatterns = [path("compute/", home, name="compute_home"), path("compute/day/<str:day>/", day_detail, name="compute_day")]

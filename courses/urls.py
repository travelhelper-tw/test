from django.urls import path

from . import views

app_name = "courses"

urlpatterns = [
    path("", views.home, name="home"),
    path(
        "courses/<int:course_id>/lectures/<int:lecture_id>/",
        views.lecture_detail, name="lecture_detail",
    ),
    path(
        "courses/<int:course_id>/lectures/<int:lecture_id>/complete/",
        views.complete, name="complete",
    ),
]

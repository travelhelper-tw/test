from django.urls import path

from . import views, commerce_views, media_views
from .legal import legal_page

app_name = "courses"

urlpatterns = [
    path("", views.home, name="home"),
    path("terms/", legal_page, {"page": "terms"}, name="terms"),
    path("privacy/", legal_page, {"page": "privacy"}, name="privacy"),
    path("refunds/", legal_page, {"page": "refunds"}, name="refunds"),
    path("courses/<int:course_id>/", commerce_views.sales, name="sales"),
    path("courses/<int:course_id>/checkout/", commerce_views.checkout, name="checkout"),
    path("orders/", commerce_views.orders, name="orders"),
    path("orders/<uuid:order_id>/", commerce_views.order_detail, name="order_detail"),
    path("library/", commerce_views.library, name="library"),
    path("payments/ecpay/notify/", commerce_views.payment_notify, name="payment_notify"),
    path("audio/<path:name>/", media_views.audio, name="audio"),
    path(
        "courses/<int:course_id>/lectures/<int:lecture_id>/",
        views.lecture_detail, name="lecture_detail",
    ),
    path(
        "courses/<int:course_id>/lectures/<int:lecture_id>/complete/",
        views.complete, name="complete",
    ),
]

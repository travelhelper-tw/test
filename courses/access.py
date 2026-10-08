from django.conf import settings

from .models import Purchase


def readable_purchases(user):
    purchases = Purchase.objects.filter(user=user, active=True)
    if settings.ECPAY_ENVIRONMENT == "production":
        purchases = purchases.filter(is_test=False)
    return purchases


def can_read_course(user, course_id):
    return user.is_authenticated and (
        user.is_superuser
        or readable_purchases(user).filter(course_id=course_id).exists()
    )

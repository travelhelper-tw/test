from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ImproperlyConfigured
from django.db import IntegrityError, transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .access import can_read_course, readable_purchases
from .models import Course, Order, PaymentNotification, Purchase
from .payments import checkout_parameters, payment_config, verified_notification


@never_cache
@require_GET
def sales(request, course_id):
    course = get_object_or_404(Course, pk=course_id)
    has_access = can_read_course(request.user, course.pk)
    return render(request, "courses/sales.html", {
        "course": course,
        "has_access": has_access,
        "first": course.lectures.order_by("order", "pk").first() if has_access else None,
        "is_test": settings.ECPAY_ENVIRONMENT == "test",
    })


@never_cache
@login_required
@require_POST
def checkout(request, course_id):
    course = get_object_or_404(Course, pk=course_id)
    if can_read_course(request.user, course.pk):
        return redirect("courses:sales", course.pk)
    if course.price is None or not 1 <= course.price <= 20000000:
        return HttpResponse("本課程尚未設定有效售價。", status=400)
    if not course.lectures.exists():
        return HttpResponse("課程尚未準備完成。", status=400)
    try:
        gateway = payment_config()
    except ImproperlyConfigured:
        return HttpResponse("付款服務尚未設定完成，請聯絡管理員。", status=503)
    order = Order.objects.create(
        user=request.user, course=course, course_title=course.title,
        amount=course.price, merchant_id=settings.ECPAY_MERCHANT_ID,
        is_test=settings.ECPAY_ENVIRONMENT == "test",
    )
    return render(request, "courses/checkout.html", {
        "order": order, "gateway": gateway, "parameters": checkout_parameters(order),
    })


@never_cache
@login_required
@require_GET
def order_detail(request, order_id):
    order = get_object_or_404(Order.objects.select_related("course"), pk=order_id, user=request.user)
    return render(request, "courses/order_detail.html", {
        "order": order, "has_access": can_read_course(request.user, order.course_id),
    })


@never_cache
@login_required
@require_GET
def orders(request):
    return render(request, "courses/orders.html", {
        "orders": Order.objects.filter(user=request.user).select_related("course"),
    })


@never_cache
@login_required
@require_GET
def library(request):
    return render(request, "courses/library.html", {
        "purchases": readable_purchases(request.user).select_related("course"),
    })


@csrf_exempt
@require_POST
def payment_notify(request):
    try:
        parameters = verified_notification(request.POST)
        with transaction.atomic():
            order = Order.objects.select_for_update().get(
                merchant_trade_no=parameters["MerchantTradeNo"]
            )
            amount = int(parameters["TradeAmt"])
            trade_no = parameters["TradeNo"]
            if (
                order.merchant_id != parameters["MerchantID"]
                or order.is_test != (settings.ECPAY_ENVIRONMENT == "test")
                or amount != order.amount
                or (order.gateway_trade_no and order.gateway_trade_no != trade_no)
            ):
                raise ValueError("訂單資訊不符。")
            if Order.objects.filter(gateway_trade_no=trade_no).exclude(pk=order.pk).exists():
                raise ValueError("交易編號已屬於其他訂單。")
            notification, created = PaymentNotification.objects.get_or_create(
                check_mac=parameters["CheckMacValue"].upper(),
                defaults={
                    "order": order, "trade_no": trade_no, "amount": amount,
                    "rtn_code": int(parameters["RtnCode"]),
                    "simulated": parameters["SimulatePaid"] == "1",
                    "payment_type": parameters["PaymentType"],
                },
            )
            if not created:
                return HttpResponse("1|OK", content_type="text/plain")
            # 綠界後台的模擬通知不是實際扣款，即使驗簽成功也不開通。
            if notification.simulated:
                return HttpResponse("1|OK", content_type="text/plain")
            order.gateway_trade_no = trade_no
            if notification.rtn_code == 1:
                if order.status != Order.Status.PAID:
                    order.status = Order.Status.PAID
                    order.paid_at = timezone.now()
                    Purchase.objects.update_or_create(
                        user=order.user, course=order.course,
                        defaults={"active": True, "order": order, "is_test": order.is_test},
                    )
                    notification.applied = True
                    notification.save(update_fields=["applied"])
            elif order.status != Order.Status.PAID:
                order.status = Order.Status.FAILED
            order.save(update_fields=["gateway_trade_no", "status", "paid_at"])
    except ImproperlyConfigured:
        return HttpResponse("0|Not configured", status=503, content_type="text/plain")
    except (ValueError, Order.DoesNotExist, IntegrityError):
        return HttpResponse("0|Invalid notification", status=400, content_type="text/plain")
    return HttpResponse("1|OK", content_type="text/plain")

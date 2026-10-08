import hashlib
import hmac
import re
from urllib.parse import quote_plus, urlsplit
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.urls import reverse
from django.utils import timezone

GATEWAYS = {
    "test": "https://payment-stage.ecpay.com.tw/Cashier/AioCheckOut/V5",
    "production": "https://payment.ecpay.com.tw/Cashier/AioCheckOut/V5",
}


def check_mac_value(parameters, hash_key=None, hash_iv=None):
    hash_key = settings.ECPAY_HASH_KEY if hash_key is None else hash_key
    hash_iv = settings.ECPAY_HASH_IV if hash_iv is None else hash_iv
    fields = sorted(
        ((key, str(value)) for key, value in parameters.items() if key.lower() != "checkmacvalue"),
        key=lambda field: field[0].lower(),
    )
    raw = "&".join([f"HashKey={hash_key}"] + [
        f"{key}={value}" for key, value in fields
    ] + [f"HashIV={hash_iv}"])
    encoded = quote_plus(raw, safe="-_.!*()").replace("~", "%7e").lower()
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest().upper()


def payment_config():
    origin = urlsplit(settings.SITE_URL)
    if (
        settings.ECPAY_ENVIRONMENT not in GATEWAYS
        or not all([settings.ECPAY_MERCHANT_ID, settings.ECPAY_HASH_KEY, settings.ECPAY_HASH_IV])
        or origin.scheme != "https" or not origin.hostname
        or origin.username or origin.password or origin.query or origin.fragment
        or origin.path not in {"", "/"}
        or len(settings.SITE_URL) > 150
        or len(settings.ECPAY_MERCHANT_ID) > 20
    ):
        raise ImproperlyConfigured("請設定綠界環境、金鑰與公開 HTTPS SITE_URL。")
    return GATEWAYS[settings.ECPAY_ENVIRONMENT]


def checkout_parameters(order):
    parameters = {
        "MerchantID": order.merchant_id,
        "MerchantTradeNo": order.merchant_trade_no,
        "MerchantTradeDate": timezone.localtime(
            order.created_at, ZoneInfo("Asia/Taipei")
        ).strftime("%Y/%m/%d %H:%M:%S"),
        "PaymentType": "aio",
        "TotalAmount": str(order.amount),
        "TradeDesc": "CoursePurchase",
        "ItemName": f"整套課程 {order.course_id}",
        "ReturnURL": settings.SITE_URL + reverse("courses:payment_notify"),
        "ClientBackURL": settings.SITE_URL + reverse("courses:order_detail", args=[order.pk]),
        "ChoosePayment": "Credit",
        "EncryptType": "1",
        "NeedExtraPaidInfo": "N",
    }
    parameters["CheckMacValue"] = check_mac_value(parameters)
    return parameters


def verified_notification(post):
    if not settings.ECPAY_HASH_KEY or not settings.ECPAY_HASH_IV or not settings.ECPAY_MERCHANT_ID:
        raise ImproperlyConfigured("尚未設定綠界付款通知金鑰。")
    if any(len(values) != 1 for _, values in post.lists()):
        raise ValueError("不接受重複的通知欄位。")
    parameters = post.dict()
    if any(key.lower() == "checkmacvalue" and key != "CheckMacValue" for key in parameters):
        raise ValueError("通知欄位名稱不正確。")
    mac = parameters.get("CheckMacValue", "")
    if not re.fullmatch(r"[A-Fa-f0-9]{64}", mac):
        raise ValueError("缺少檢查碼。")
    if not hmac.compare_digest(check_mac_value(parameters), mac.upper()):
        raise ValueError("檢查碼不符。")
    if parameters.get("MerchantID") != settings.ECPAY_MERCHANT_ID:
        raise ValueError("商店代號不符。")
    if not re.fullmatch(r"[A-Za-z0-9]{1,20}", parameters.get("MerchantTradeNo", "")):
        raise ValueError("商店訂單編號不正確。")
    if not re.fullmatch(r"[A-Za-z0-9]{1,20}", parameters.get("TradeNo", "")):
        raise ValueError("綠界交易編號不正確。")
    if not re.fullmatch(r"[0-9]{1,8}", parameters.get("TradeAmt", "")):
        raise ValueError("金額格式不正確。")
    if not re.fullmatch(r"(?:0|[1-9][0-9]{0,8})", parameters.get("RtnCode", "")):
        raise ValueError("付款結果格式不正確。")
    if parameters.get("SimulatePaid") not in {"0", "1"}:
        raise ValueError("缺少模擬付款標記。")
    if parameters.get("PaymentType") != "Credit_CreditCard":
        raise ValueError("本網站僅支援信用卡一次付款。")
    return parameters

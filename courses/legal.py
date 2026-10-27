from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.shortcuts import render
from django.views.decorators.http import require_GET

POLICY_VERSION = "2026-10-27"
PAGES = {
    "terms": "服務條款",
    "privacy": "隱私權政策",
    "refunds": "退款與客服政策",
}


def legal_ready():
    try:
        validate_email(settings.SUPPORT_EMAIL)
    except ValidationError:
        return False
    return bool(
        settings.LEGAL_REVIEWED and settings.SELLER_NAME.strip()
        and settings.SELLER_ADDRESS.strip()
    )


def legal_context(request):
    return {
        "policy_version": POLICY_VERSION,
        "legal_ready": legal_ready(),
        "seller_name": settings.SELLER_NAME,
        "seller_address": settings.SELLER_ADDRESS,
        "support_email": settings.SUPPORT_EMAIL,
    }


@require_GET
def legal_page(request, page):
    return render(request, f"courses/legal/{page}.html", {"legal_title": PAGES[page]})

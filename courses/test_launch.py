from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.urls import reverse

from .legal import POLICY_VERSION
from .models import Course, Lecture, Order
from .test_commerce import PAYMENT_SETTINGS


@override_settings(**PAYMENT_SETTINGS)
class LegalAndSalesTests(TestCase):
    def setUp(self):
        self.course = Course.objects.create(title="法律頁面測試課程", price=3680)
        Lecture.objects.create(course=self.course, chapter_label="第一章", title="隱藏內容", content="付費秘密文字")
        self.user = get_user_model().objects.create_user(username="legal-reader")
        self.url = reverse("courses:checkout", args=[self.course.pk])
        self.consent = {"accept_terms": "yes", "policy_version": POLICY_VERSION}

    def test_public_legal_pages_and_footer_without_login(self):
        for name in ["terms", "privacy", "refunds"]:
            response = self.client.get(reverse(f"courses:{name}"))
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, POLICY_VERSION)
            self.assertContains(response, "待審核範本")
        response = self.client.get(reverse("courses:home"))
        for name in ["terms", "privacy", "refunds"]:
            self.assertContains(response, reverse(f"courses:{name}"))

    def test_sales_information_does_not_expose_chapters_or_auto_accept(self):
        response = self.client.get(reverse("courses:sales", args=[self.course.pk]))
        self.assertContains(response, "營運與法律資料尚待確認")
        self.client.force_login(self.user)
        response = self.client.get(reverse("courses:sales", args=[self.course.pk]))
        for text in ["NT$ 3680", "1 個章節", "不提供免費試聽", 'name="accept_terms"']:
            self.assertContains(response, text)
        self.assertNotContains(response, "付費秘密文字")
        self.assertNotContains(response, "隱藏內容")
        self.assertNotContains(response, " checked")

    def test_checkout_requires_current_explicit_confirmation(self):
        self.client.force_login(self.user)
        for data in [{}, {"accept_terms": "yes"}, {"accept_terms": "yes", "policy_version": "old"}]:
            self.assertEqual(self.client.post(self.url, data).status_code, 400)
        self.assertFalse(Order.objects.exists())
        self.assertEqual(self.client.post(self.url, self.consent).status_code, 200)
        order = Order.objects.get()
        self.assertEqual(order.policy_version, POLICY_VERSION)
        self.assertIsNotNone(order.terms_accepted_at)
        self.assertEqual(order.amount, 3680)

    def test_production_checkout_fails_closed_until_reviewed(self):
        self.client.force_login(self.user)
        with override_settings(ECPAY_ENVIRONMENT="production", LEGAL_REVIEWED=False):
            self.assertEqual(self.client.post(self.url, self.consent).status_code, 503)
        with override_settings(ECPAY_ENVIRONMENT="production", LEGAL_REVIEWED=True, SELLER_NAME="營運者", SELLER_ADDRESS="聯絡地址", SUPPORT_EMAIL="invalid"):
            self.assertEqual(self.client.post(self.url, self.consent).status_code, 503)
        self.assertFalse(Order.objects.exists())
        with override_settings(ECPAY_ENVIRONMENT="production", LEGAL_REVIEWED=True, SELLER_NAME="營運者", SELLER_ADDRESS="聯絡地址", SUPPORT_EMAIL="support@example.com"):
            response = self.client.post(self.url, self.consent)
            self.assertContains(response, "https://payment.ecpay.com.tw/Cashier/AioCheckOut/V5")
            self.assertFalse(Order.objects.get().is_test)
            response = self.client.get(reverse("courses:terms"))
            self.assertNotContains(response, "待審核範本")

    def test_operator_information_is_escaped(self):
        with override_settings(SELLER_NAME="<script>bad</script>"):
            response = self.client.get(reverse("courses:privacy"))
            self.assertContains(response, "&lt;script&gt;bad&lt;/script&gt;")


@override_settings(**PAYMENT_SETTINGS)
class LaunchCheckTests(TestCase):
    def test_local_settings_rejected_without_printing_secrets(self):
        with override_settings(DEBUG=True, USE_X_ACCEL_REDIRECT=False, LEGAL_REVIEWED=False):
            with self.assertRaises(CommandError) as error:
                call_command("check_launch", production=True, stdout=StringIO())
        message = str(error.exception)
        self.assertIn("DEBUG=False", message)
        self.assertIn("法律審核", message)
        self.assertNotIn(PAYMENT_SETTINGS["ECPAY_HASH_KEY"], message)

    def test_ready_stage_and_production_and_public_private_overlap(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "static/css").mkdir(parents=True)
            (root / "static/css/style.css").write_text("body {}")
            (root / "private").mkdir()
            with override_settings(
                DEBUG=False, ALLOWED_HOSTS=["courses.example.com"],
                USE_X_ACCEL_REDIRECT=True, STATIC_ROOT=root / "static",
                PRIVATE_MEDIA_ROOT=root / "private",
            ):
                call_command("check_launch", stdout=StringIO())
                with override_settings(ECPAY_ENVIRONMENT="production", LEGAL_REVIEWED=True, SELLER_NAME="營運者", SELLER_ADDRESS="聯絡地址", SUPPORT_EMAIL="support@example.com"):
                    call_command("check_launch", production=True, stdout=StringIO())
                with override_settings(PRIVATE_MEDIA_ROOT=root / "static/private"):
                    (root / "static/private").mkdir()
                    with self.assertRaisesMessage(CommandError, "不可互相包含"):
                        call_command("check_launch", stdout=StringIO())
                with override_settings(ALLOWED_HOSTS=["wrong.example.com"]):
                    with self.assertRaisesMessage(CommandError, "SITE_URL"):
                        call_command("check_launch", stdout=StringIO())

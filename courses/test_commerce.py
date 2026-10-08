from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connections
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse

from .models import Course, Lecture, Order, Purchase, PaymentNotification, Progress
from .payments import check_mac_value


PAYMENT_SETTINGS = {
    "ECPAY_ENVIRONMENT": "test",
    "ECPAY_MERCHANT_ID": "unit-test-merchant",
    "ECPAY_HASH_KEY": "unit-test-key",
    "ECPAY_HASH_IV": "unit-test-iv",
    "SITE_URL": "https://courses.example.com",
}


class CheckMacTests(TestCase):
    def test_dotnet_encoding_matches_independent_php_reference(self):
        parameters = {
            "MerchantID": "unit-test-merchant",
            "ItemName": "中文 + ~ ' !*()_-.",
            "TotalAmount": "1200",
            "Empty": "",
        }
        expected = "FCB9B99D9BC58212DDB8DF813A6DEC66E4554EC0DCFDCFF5B7A1776E2982F510"
        self.assertEqual(check_mac_value(parameters, "unit-test-key", "unit-test-iv"), expected)
        parameters["CheckMacValue"] = expected
        self.assertEqual(
            check_mac_value(dict(reversed(list(parameters.items()))), "unit-test-key", "unit-test-iv"),
            expected,
        )


@override_settings(**PAYMENT_SETTINGS)
class CommerceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username="buyer")
        cls.other = get_user_model().objects.create_user(username="outsider")
        cls.course = Course.objects.create(
            title="購買測試課程", price=1200, description="公開介紹 <script>不執行</script>"
        )
        cls.lecture = Lecture.objects.create(
            course=cls.course, title="付費章節", chapter_label="第一章",
            content="<p>只有購買者可見的內容</p>",
        )

    def setUp(self):
        self.client.force_login(self.user)

    def checkout(self):
        response = self.client.post(reverse("courses:checkout", args=[self.course.pk]))
        self.assertEqual(response.status_code, 200)
        return response, response.context["order"]

    def payload(self, order, **changes):
        data = {
            "MerchantID": order.merchant_id,
            "MerchantTradeNo": order.merchant_trade_no,
            "TradeNo": "ECP" + order.merchant_trade_no[:17],
            "TradeAmt": str(order.amount),
            "RtnCode": "1",
            "RtnMsg": "Succeeded",
            "SimulatePaid": "0",
            "PaymentType": "Credit_CreditCard",
            "PaymentDate": "2026/10/07 15:00:00",
        }
        data.update(changes)
        data["CheckMacValue"] = check_mac_value(data)
        return data

    def notify(self, data):
        client = Client(enforce_csrf_checks=True)
        return client.post(reverse("courses:payment_notify"), data)

    def test_checkout_price_is_server_snapshot_and_form_has_no_secrets(self):
        response, order = self.checkout()
        self.assertEqual(order.amount, 1200)
        self.assertEqual(len(order.merchant_trade_no), 20)
        fields = response.context["parameters"]
        self.assertEqual(fields["TotalAmount"], "1200")
        self.assertEqual(fields["CheckMacValue"], check_mac_value(fields))
        self.assertEqual(fields["ChoosePayment"], "Credit")
        self.assertEqual(fields["EncryptType"], "1")
        self.assertEqual(fields["ReturnURL"], "https://courses.example.com/payments/ecpay/notify/")
        self.assertContains(response, "https://payment-stage.ecpay.com.tw/Cashier/AioCheckOut/V5")
        self.assertNotContains(response, PAYMENT_SETTINGS["ECPAY_HASH_KEY"])
        self.assertNotContains(response, PAYMENT_SETTINGS["ECPAY_HASH_IV"])
        self.assertFalse(Purchase.objects.exists())
        self.course.price = 2400
        self.course.save()
        self.assertEqual(self.notify(self.payload(order)).content, b"1|OK")
        self.assertEqual(Purchase.objects.get().order_id, order.pk)

    def test_payment_success_grants_course_and_records_verified_notification(self):
        _, order = self.checkout()
        response = self.notify(self.payload(order))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"1|OK")
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PAID)
        self.assertIsNotNone(order.paid_at)
        self.assertTrue(Purchase.objects.get(user=self.user, course=self.course).is_test)
        self.assertTrue(PaymentNotification.objects.get().applied)
        self.assertContains(self.client.get(reverse(
            "courses:lecture_detail", args=[self.course.pk, self.lecture.pk]
        )), "只有購買者可見的內容")

    def test_duplicate_and_delayed_notifications_never_restore_revoked_access(self):
        _, order = self.checkout()
        data = self.payload(order)
        self.notify(data)
        purchase = Purchase.objects.get()
        purchase.active = False
        purchase.save()
        for payload in [data, self.payload(order, RtnMsg="Repeated success")]:
            self.assertEqual(self.notify(payload).content, b"1|OK")
        purchase.refresh_from_db()
        self.assertFalse(purchase.active)
        self.assertEqual(Purchase.objects.count(), 1)
        self.assertEqual(PaymentNotification.objects.filter(applied=True).count(), 1)

    def test_failed_payment_is_recorded_without_access_and_can_later_succeed(self):
        _, order = self.checkout()
        self.assertEqual(self.notify(self.payload(order, RtnCode="10100058")).content, b"1|OK")
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.FAILED)
        self.assertFalse(Purchase.objects.exists())
        self.assertEqual(self.notify(self.payload(order)).content, b"1|OK")
        self.assertTrue(Purchase.objects.get().active)
        self.notify(self.payload(order, RtnCode="10100058", RtnMsg="Late failure"))
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PAID)

    def test_simulated_payment_never_fulfills_even_in_stage(self):
        _, order = self.checkout()
        self.assertEqual(self.notify(self.payload(order, SimulatePaid="1")).content, b"1|OK")
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PENDING)
        self.assertFalse(Purchase.objects.exists())
        self.assertTrue(PaymentNotification.objects.get().simulated)
        self.assertFalse(PaymentNotification.objects.get().applied)

    def test_forged_and_mismatched_notifications_are_rejected_without_changes(self):
        _, order = self.checkout()
        forged = self.payload(order)
        forged["TradeAmt"] = "1"
        invalid = [
            forged,
            self.payload(order, MerchantID="wrong"),
            self.payload(order, MerchantTradeNo="unknown"),
            self.payload(order, TradeAmt="1199"),
            self.payload(order, TradeNo=""),
            self.payload(order, SimulatePaid=""),
            self.payload(order, PaymentType="ATM"),
            self.payload(order, RtnCode="01"),
            self.payload(order, RtnCode="99999999999"),
        ]
        for data in invalid:
            with self.subTest(data=data):
                self.assertEqual(self.notify(data).status_code, 400)
        self.assertFalse(Purchase.objects.exists())
        self.assertFalse(PaymentNotification.objects.exists())
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PENDING)

    def test_extra_callback_fields_are_signed_and_duplicate_fields_rejected(self):
        _, order = self.checkout()
        data = self.payload(order, CustomField1="中文 + ~ ' !")
        response = self.notify(data)
        self.assertEqual(response.content, b"1|OK")
        data["CustomField1"] = "tampered"
        self.assertEqual(self.notify(data).status_code, 400)
        data = self.payload(order)
        data["TradeAmt"] = [str(order.amount), str(order.amount)]
        self.assertEqual(self.notify(data).status_code, 400)

    def test_trade_number_binding_rejects_conflicting_and_reused_transactions(self):
        _, order = self.checkout()
        self.notify(self.payload(order))
        self.assertEqual(self.notify(self.payload(order, TradeNo="another")).status_code, 400)
        Purchase.objects.all().delete()
        _, another = self.checkout()
        self.assertEqual(
            self.notify(self.payload(another, TradeNo=order.gateway_trade_no or self.payload(order)["TradeNo"])).status_code,
            400,
        )
        self.assertFalse(Purchase.objects.exists())

    def test_transaction_rolls_back_if_fulfillment_fails(self):
        _, order = self.checkout()
        with patch("courses.commerce_views.Purchase.objects.update_or_create", side_effect=RuntimeError("database failure")):
            with self.assertRaises(RuntimeError):
                self.notify(self.payload(order))
        self.assertFalse(PaymentNotification.objects.exists())
        self.assertFalse(Purchase.objects.exists())
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PENDING)
        self.assertEqual(self.notify(self.payload(order)).content, b"1|OK")

    def test_return_page_does_not_confirm_payment_and_orders_are_private(self):
        _, order = self.checkout()
        url = reverse("courses:order_detail", args=[order.pk])
        response = self.client.get(url, {"RtnCode": "1", "TradeAmt": "1200"})
        self.assertContains(response, "待付款")
        self.assertFalse(Purchase.objects.exists())
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertNotContains(self.client.get(reverse("courses:orders")), order.merchant_trade_no)

    def test_checkout_requires_csrf_post_auth_and_config_and_positive_price(self):
        url = reverse("courses:checkout", args=[self.course.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.post(url).status_code, 403)
        client.logout()
        self.assertEqual(Client().post(url).status_code, 302)
        with override_settings(ECPAY_HASH_KEY=""):
            self.assertEqual(self.client.post(url).status_code, 503)
            self.assertEqual(self.notify({}).status_code, 503)
        with override_settings(SITE_URL="http://unsafe.example.com"):
            self.assertEqual(self.client.post(url).status_code, 503)
        for price in [None, 0, 20000001]:
            self.course.price = price
            self.course.save()
            self.assertEqual(self.client.post(url).status_code, 400)
        self.assertFalse(Order.objects.exists())

    def test_environment_isolation_for_callback_access_and_library(self):
        _, order = self.checkout()
        self.notify(self.payload(order))
        with override_settings(ECPAY_ENVIRONMENT="production"):
            self.assertEqual(self.notify(self.payload(order)).status_code, 400)
            url = reverse("courses:lecture_detail", args=[self.course.pk, self.lecture.pk])
            self.assertRedirects(self.client.get(url), reverse("courses:sales", args=[self.course.pk]))
            self.assertNotContains(self.client.get(reverse("courses:library")), self.course.title)

    def test_public_sales_escape_description_and_never_show_lecture_content(self):
        self.client.logout()
        response = self.client.get(reverse("courses:sales", args=[self.course.pk]))
        self.assertContains(response, "NT$ 1200")
        self.assertContains(response, "&lt;script&gt;")
        self.assertNotContains(response, "<script>不執行")
        self.assertNotContains(response, self.lecture.content)
        self.assertNotContains(response, self.lecture.title)

    def test_unpurchased_and_revoked_readers_cannot_read_or_mark_progress(self):
        read = reverse("courses:lecture_detail", args=[self.course.pk, self.lecture.pk])
        complete = reverse("courses:complete", args=[self.course.pk, self.lecture.pk])
        sales = reverse("courses:sales", args=[self.course.pk])
        for active in [None, False]:
            if active is False:
                Purchase.objects.create(user=self.user, course=self.course, active=False)
            self.assertRedirects(self.client.get(read), sales)
            self.assertRedirects(self.client.post(complete), sales)
        self.assertFalse(Progress.objects.exists())

    def test_library_only_lists_active_own_purchases_and_prevents_rebuy(self):
        Purchase.objects.create(user=self.other, course=self.course)
        self.assertNotContains(self.client.get(reverse("courses:library")), self.course.title)
        Purchase.objects.create(user=self.user, course=self.course)
        self.assertContains(self.client.get(reverse("courses:library")), self.course.title)
        self.assertRedirects(
            self.client.post(reverse("courses:checkout", args=[self.course.pk])),
            reverse("courses:sales", args=[self.course.pk]),
        )
        self.assertFalse(Order.objects.exists())

    def test_financial_records_readonly_and_purchase_management_superuser_only(self):
        request = type("Request", (), {"user": self.user})()
        for model in [Order, PaymentNotification]:
            model_admin = admin.site._registry[model]
            self.assertFalse(model_admin.has_add_permission(request))
            self.assertFalse(model_admin.has_change_permission(request))
            self.assertFalse(model_admin.has_delete_permission(request))
        purchase_admin = admin.site._registry[Purchase]
        self.user.is_staff = True
        self.assertFalse(purchase_admin.has_add_permission(request))
        self.assertFalse(purchase_admin.has_change_permission(request))
        self.user.is_superuser = True
        self.assertTrue(purchase_admin.has_add_permission(request))
        purchase = Purchase.objects.create(user=self.other, course=self.course)
        queryset = Purchase.objects.filter(pk=purchase.pk)
        purchase_admin.revoke_access(request, queryset)
        purchase.refresh_from_db()
        self.assertFalse(purchase.active)
        purchase_admin.grant_access(request, queryset)
        purchase.refresh_from_db()
        self.assertTrue(purchase.active)


class PrivateAudioTests(TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.settings_override = override_settings(
            MEDIA_ROOT=self.root / "media", PRIVATE_MEDIA_ROOT=self.root / "private",
            USE_X_ACCEL_REDIRECT=False,
        )
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.user = get_user_model().objects.create_user(username="listener")
        self.course = Course.objects.create(title="有聲課程")
        self.lecture = Lecture.objects.create(course=self.course, chapter_label="第一章", title="音訊")
        # Field storage is resolved at model import; replace it while testing temporary directories.
        storage = self.lecture._meta.get_field("audio").storage
        from .storage import private_audio_storage
        self.lecture._meta.get_field("audio").storage = private_audio_storage()
        self.addCleanup(setattr, self.lecture._meta.get_field("audio"), "storage", storage)
        self.lecture.refresh_from_db()
        self.lecture.audio.save("測試 +.mp3", ContentFile(b"ID3-local-placeholder"), save=True)
        self.url = self.lecture.audio.url
        self.client.force_login(self.user)

    def test_private_storage_and_audio_authorization(self):
        self.assertTrue(Path(self.lecture.audio.path).is_relative_to(self.root / "private"))
        self.assertEqual(self.client.get(self.url).status_code, 403)
        Purchase.objects.create(user=self.user, course=self.course)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(response.streaming_content), b"ID3-local-placeholder")
        self.assertIn("no-store", response["Cache-Control"])
        Purchase.objects.filter(user=self.user).update(active=False)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 302)

    def test_wrong_course_purchase_does_not_authorize_audio(self):
        other = Course.objects.create(title="其他")
        Purchase.objects.create(user=self.user, course=other)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_internal_redirect_is_escaped_and_legacy_urls_are_blocked(self):
        Purchase.objects.create(user=self.user, course=self.course)
        with override_settings(USE_X_ACCEL_REDIRECT=True):
            response = self.client.get(self.url)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response["X-Accel-Redirect"].startswith("/_private_audio/audio/"))
            self.assertNotIn(" ", response["X-Accel-Redirect"])
        for url in ["/media/audio/demo.mp3", "/_private_audio/audio/demo.mp3"]:
            self.assertEqual(self.client.get(url).status_code, 404)

    def test_missing_and_traversal_audio_never_served(self):
        Purchase.objects.create(user=self.user, course=self.course)
        for name in ["audio/missing.mp3", "../outside.mp3"]:
            Lecture.objects.filter(pk=self.lecture.pk).update(audio=name)
            response = self.client.get(reverse("courses:audio", kwargs={"name": name}))
            self.assertEqual(response.status_code, 404)

    def test_migration_moves_verifies_removes_and_is_repeatable(self):
        name = "audio/legacy.mp3"
        source = self.root / "media" / name
        source.parent.mkdir(parents=True)
        source.write_bytes(b"legacy-audio")
        Lecture.objects.filter(pk=self.lecture.pk).update(audio=name)
        call_command("migrate_private_audio", dry_run=True, stdout=StringIO())
        self.assertTrue(source.exists())
        self.assertFalse((self.root / "private" / name).exists())
        call_command("migrate_private_audio", stdout=StringIO())
        self.assertFalse(source.exists())
        self.assertEqual((self.root / "private" / name).read_bytes(), b"legacy-audio")
        call_command("migrate_private_audio", stdout=StringIO())

    def test_migration_never_overwrites_conflicting_private_file(self):
        name = self.lecture.audio.name
        source = self.root / "media" / name
        source.parent.mkdir(parents=True)
        source.write_bytes(b"conflicting-public-copy")
        with self.assertRaises(CommandError):
            call_command("migrate_private_audio", stdout=StringIO())
        self.assertTrue(source.exists())
        self.assertEqual(Path(self.lecture.audio.path).read_bytes(), b"ID3-local-placeholder")


@override_settings(**PAYMENT_SETTINGS)
class ConcurrentNotificationTests(TransactionTestCase):
    def test_parallel_retries_only_fulfill_once(self):
        user = get_user_model().objects.create_user(username="concurrent-buyer")
        course = Course.objects.create(title="並行通知測試", price=1200)
        order = Order.objects.create(
            user=user, course=course, course_title=course.title, amount=1200,
            merchant_id=PAYMENT_SETTINGS["ECPAY_MERCHANT_ID"],
        )
        data = {
            "MerchantID": order.merchant_id, "MerchantTradeNo": order.merchant_trade_no,
            "TradeNo": "concurrent123", "TradeAmt": "1200", "RtnCode": "1",
            "SimulatePaid": "0", "PaymentType": "Credit_CreditCard",
        }
        data["CheckMacValue"] = check_mac_value(data)

        def send_notification(_):
            try:
                response = Client().post(reverse("courses:payment_notify"), data)
                return response.status_code, response.content
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(send_notification, range(2)))
        self.assertEqual(results, [(200, b"1|OK"), (200, b"1|OK")])
        self.assertEqual(Purchase.objects.count(), 1)
        self.assertEqual(PaymentNotification.objects.filter(applied=True).count(), 1)

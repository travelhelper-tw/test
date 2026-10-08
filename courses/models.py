import uuid

from django.db import models
from django.conf import settings
from django.core.validators import FileExtensionValidator, MinValueValidator, MaxValueValidator

from .storage import private_audio_storage


def merchant_trade_number():
    return uuid.uuid4().hex[:20]


class Course(models.Model):
    title = models.CharField("課程名稱", max_length=200)
    description = models.TextField("公開銷售介紹", blank=True)
    price = models.PositiveIntegerField(
        "整套售價（新臺幣元）", null=True, blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(20000000)],
        help_text="留空不開放結帳；一次付款，購買權限無到期日。",
    )

    class Meta:
        verbose_name = "課程"
        verbose_name_plural = "課程"

    def __str__(self):
        return self.title


class Lecture(models.Model):
    course = models.ForeignKey(
        Course, on_delete=models.CASCADE, related_name="lectures", verbose_name="課程"
    )
    chapter_label = models.CharField("章節標籤", max_length=50)
    title = models.CharField("標題", max_length=200)
    audio = models.FileField(
        "音訊 MP3", upload_to="audio/", blank=True, storage=private_audio_storage,
        validators=[FileExtensionValidator(["mp3"])],
    )
    cover = models.ImageField(
        "書封", upload_to="covers/", blank=True,
        validators=[FileExtensionValidator(["jpg", "jpeg", "png", "webp"])],
    )
    content = models.TextField(
        "內容簡介（HTML）", blank=True, help_text="僅限受信任的管理員輸入 HTML。"
    )
    order = models.PositiveIntegerField("排序", default=0)

    class Meta:
        ordering = ["order"]
        verbose_name = "章節"
        verbose_name_plural = "章節"

    def __str__(self):
        return f"{self.chapter_label}：{self.title}"


class Progress(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name="使用者"
    )
    lecture = models.ForeignKey(Lecture, on_delete=models.CASCADE, verbose_name="章節")
    completed = models.BooleanField("已完成", default=False)

    class Meta:
        unique_together = ("user", "lecture")
        verbose_name = "閱讀進度"
        verbose_name_plural = "閱讀進度"

    def __str__(self):
        return f"{self.user} — {self.lecture}"


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "待付款"
        PAID = "paid", "已付款"
        FAILED = "failed", "付款失敗"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant_trade_no = models.CharField(
        "商店訂單編號", max_length=20, unique=True, default=merchant_trade_number,
        editable=False,
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, verbose_name="使用者")
    course = models.ForeignKey(Course, on_delete=models.PROTECT, verbose_name="課程")
    course_title = models.CharField("購買時課程名稱", max_length=200)
    amount = models.PositiveIntegerField("訂單金額（新臺幣元）")
    merchant_id = models.CharField("綠界商店代號", max_length=20)
    is_test = models.BooleanField("測試環境", default=True)
    status = models.CharField("付款狀態", max_length=10, choices=Status.choices, default=Status.PENDING)
    gateway_trade_no = models.CharField("綠界交易編號", max_length=20, unique=True, null=True, blank=True)
    created_at = models.DateTimeField("建立時間", auto_now_add=True)
    paid_at = models.DateTimeField("付款時間", null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "訂單"
        verbose_name_plural = "訂單"

    def __str__(self):
        return self.merchant_trade_no


class Purchase(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name="使用者")
    course = models.ForeignKey(Course, on_delete=models.CASCADE, verbose_name="課程")
    active = models.BooleanField("有效購買權限", default=True)
    is_test = models.BooleanField("僅限測試環境的權限", default=False)
    order = models.ForeignKey(Order, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="來源訂單")
    updated_at = models.DateTimeField("最後異動", auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "course"], name="unique_course_purchase"),
        ]
        verbose_name = "購買權限"
        verbose_name_plural = "購買權限"

    def __str__(self):
        return f"{self.user} — {self.course}"


class PaymentNotification(models.Model):
    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name="notifications", verbose_name="訂單")
    check_mac = models.CharField("通知識別碼", max_length=64, unique=True)
    trade_no = models.CharField("綠界交易編號", max_length=20)
    amount = models.PositiveIntegerField("付款金額")
    rtn_code = models.IntegerField("付款結果代碼")
    simulated = models.BooleanField("模擬付款")
    payment_type = models.CharField("付款方式", max_length=30)
    applied = models.BooleanField("已開通課程", default=False)
    received_at = models.DateTimeField("接收時間", auto_now_add=True)

    class Meta:
        ordering = ["-received_at"]
        verbose_name = "已驗簽付款通知"
        verbose_name_plural = "已驗簽付款通知"

    def __str__(self):
        return f"{self.order} — {self.rtn_code}"

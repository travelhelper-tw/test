from django.db import models
from django.conf import settings
from django.core.validators import FileExtensionValidator


class Course(models.Model):
    title = models.CharField("課程名稱", max_length=200)

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
        "音訊 MP3", upload_to="audio/", blank=True,
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

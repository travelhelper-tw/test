from django.core.management.base import BaseCommand
from django.db import transaction

from courses.models import Course, Lecture


class Command(BaseCommand):
    help = "建立售價 NT$ 3,680 的原創佔位課程；不覆寫既有課程價格或章節。"

    @transaction.atomic
    def handle(self, *args, **options):
        course, _ = Course.objects.get_or_create(
            title="示範課程：慢讀與聆聽", defaults={"price": 3680}
        )
        titles = ["閱讀的起點", "建立聆聽習慣", "回顧與練習"]
        labels = ["第一章", "第二章", "第三章"]
        for order, (label, title) in enumerate(zip(labels, titles), start=1):
            Lecture.objects.get_or_create(
                course=course, chapter_label=label,
                defaults={
                    "title": title,
                    "order": order,
                    "content": (
                        "<p>這是原創示範佔位文字，供測試課程閱讀版面使用。</p>"
                        "<p>請由管理員替換為您擁有授權的內容，"
                        "並上傳自己的 MP3 與書封圖片。</p>"
                    ),
                },
            )
        self.stdout.write(self.style.SUCCESS("示範課程已就緒（不含音檔或圖片）。"))

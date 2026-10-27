import hashlib
import shutil
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from courses.models import Lecture


class Command(BaseCommand):
    help = "將舊 media/audio 音檔搬入私有儲存，核對後刪除公開副本；請先停止服務並備份。"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="僅檢查，不搬移或刪除。")

    def handle(self, *args, **options):
        public_root = Path(settings.MEDIA_ROOT).resolve()
        private_root = Path(settings.PRIVATE_MEDIA_ROOT).resolve()
        if private_root == public_root or public_root in private_root.parents:
            raise CommandError("私有目錄不得位於公開目錄內。")
        names = Lecture.objects.exclude(audio="").values_list("audio", flat=True).distinct()
        for name in names:
            source = (public_root / name).resolve()
            target = (private_root / name).resolve()
            if (
                not name.startswith("audio/")
                or public_root not in source.parents
                or private_root not in target.parents
            ):
                raise CommandError(f"不安全的音檔路徑：{name}")
            if not source.is_file():
                if target.is_file():
                    self.stdout.write(f"已私有化：{name}")
                    continue
                raise CommandError(f"找不到音檔：{name}")
            if target.exists() and (
                not target.is_file() or self.digest(source) != self.digest(target)
            ):
                raise CommandError(f"私有目錄已有不同內容，拒絕覆寫：{name}")
            if options["dry_run"]:
                self.stdout.write(f"待搬移：{name}")
                continue
            try:
                if not target.exists():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    created = False
                    try:
                        with source.open("rb") as src, target.open("xb") as dst:
                            created = True
                            shutil.copyfileobj(src, dst)
                    except Exception:
                        if created:
                            target.unlink(missing_ok=True)
                        raise
                if self.digest(source) != self.digest(target):
                    raise CommandError(f"內容核對失敗，保留公開副本：{name}")
                source.unlink()
            except OSError as exc:
                raise CommandError(f"搬移失敗：{name}；{exc}") from exc
            self.stdout.write(self.style.SUCCESS(f"已搬移並移除公開副本：{name}"))

    @staticmethod
    def digest(path):
        with path.open("rb") as file:
            return hashlib.file_digest(file, "sha256").digest()

from pathlib import Path
from urllib.parse import urlsplit

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.management.base import BaseCommand, CommandError

from courses.legal import legal_ready
from courses.payments import payment_config


class Command(BaseCommand):
    help = "檢查公開部署的必要設定，不會連線綠界、收款或變更資料。"

    def add_arguments(self, parser):
        parser.add_argument("--production", action="store_true", help="額外要求正式金流與已審核法律資料。")

    def handle(self, *args, **options):
        problems = []
        if settings.DEBUG:
            problems.append("公開部署須設定 DEBUG=False。")
        if not settings.ALLOWED_HOSTS or "*" in settings.ALLOWED_HOSTS:
            problems.append("ALLOWED_HOSTS 必須明確指定網域，不得為 *。")
        try:
            payment_config()
        except ImproperlyConfigured:
            problems.append("綠界資料或公開 HTTPS SITE_URL 尚未設定完整。")
        hostname = urlsplit(settings.SITE_URL).hostname
        if hostname and hostname not in settings.ALLOWED_HOSTS:
            problems.append("SITE_URL 主機名稱必須列在 ALLOWED_HOSTS。")
        if not settings.USE_X_ACCEL_REDIRECT:
            problems.append("Nginx 部署須設定 USE_X_ACCEL_REDIRECT=True。")
        for label, root in [
            ("STATIC_ROOT", settings.STATIC_ROOT),
            ("PRIVATE_MEDIA_ROOT", settings.PRIVATE_MEDIA_ROOT),
        ]:
            if not Path(root).is_dir():
                problems.append(f"{label} 目錄尚未建立。")
        if not (Path(settings.STATIC_ROOT) / "css/style.css").is_file():
            problems.append("尚未 collectstatic，找不到課程樣式。")
        private = Path(settings.PRIVATE_MEDIA_ROOT).resolve()
        for public in [settings.MEDIA_ROOT, settings.STATIC_ROOT, *settings.STATICFILES_DIRS]:
            public = Path(public).resolve()
            if private == public or public in private.parents or private in public.parents:
                problems.append("私有目錄與公開目錄不可互相包含。")
                break
        if options["production"]:
            if settings.ECPAY_ENVIRONMENT != "production":
                problems.append("正式驗收須使用 ECPAY_ENVIRONMENT=production。")
            if not legal_ready():
                problems.append("正式收款須填妥營運者／地址／客服並完成法律審核。")
        if problems:
            raise CommandError("\n".join(problems))
        self.stdout.write(self.style.SUCCESS(
            "設定檢查通過；仍須另外驗證 DNS、TLS、Nginx internal、備份還原及實際付款。"
        ))

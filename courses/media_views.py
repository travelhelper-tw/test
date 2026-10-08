from pathlib import Path
from urllib.parse import quote

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe

from .access import can_read_course
from .models import Lecture


@never_cache
@login_required
@require_safe
def audio(request, name):
    lecture = get_object_or_404(Lecture, audio=name)
    if not can_read_course(request.user, lecture.course_id):
        return HttpResponseForbidden("請先購買整套課程。")
    root = Path(settings.PRIVATE_MEDIA_ROOT).resolve()
    path = (root / lecture.audio.name).resolve()
    if root not in path.parents or not path.is_file():
        raise Http404("音檔尚未就緒。")
    if settings.USE_X_ACCEL_REDIRECT:
        response = HttpResponse(content_type="audio/mpeg")
        relative_name = path.relative_to(root).as_posix()
        response["X-Accel-Redirect"] = "/_private_audio/" + quote(relative_name, safe="/")
    else:
        response = FileResponse(path.open("rb"), content_type="audio/mpeg")
    response["X-Content-Type-Options"] = "nosniff"
    return response

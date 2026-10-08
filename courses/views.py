from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.views.decorators.cache import never_cache

from .models import Course, Lecture, Progress
from .access import can_read_course


def home(request):
    return render(request, "courses/course_list.html", {
        "courses": Course.objects.order_by("pk"),
    })


def ordered_lectures(lecture):
    return list(lecture.course.lectures.order_by("order", "pk"))


@never_cache
@login_required
def lecture_detail(request, course_id, lecture_id):
    lecture = get_object_or_404(
        Lecture.objects.select_related("course"), pk=lecture_id, course_id=course_id
    )
    if not can_read_course(request.user, course_id):
        return redirect("courses:sales", course_id)
    lectures = ordered_lectures(lecture)
    done_ids = set(Progress.objects.filter(
        user=request.user, lecture__course_id=course_id, completed=True,
    ).values_list("lecture_id", flat=True))
    index = next(i for i, item in enumerate(lectures) if item.pk == lecture.pk)
    return render(request, "courses/lecture.html", {
        "lecture": lecture,
        "lectures": lectures,
        "done_ids": done_ids,
        "percent": len(done_ids) * 100 // len(lectures),
        "prev": lectures[index - 1] if index else None,
        "next": lectures[index + 1] if index + 1 < len(lectures) else None,
    })


@login_required
@require_POST
def complete(request, course_id, lecture_id):
    lecture = get_object_or_404(
        Lecture.objects.select_related("course"), pk=lecture_id, course_id=course_id
    )
    if not can_read_course(request.user, course_id):
        return redirect("courses:sales", course_id)
    lectures = ordered_lectures(lecture)
    index = next(i for i, item in enumerate(lectures) if item.pk == lecture.pk)
    Progress.objects.update_or_create(
        user=request.user, lecture=lecture, defaults={"completed": True}
    )
    target = lectures[index + 1] if index + 1 < len(lectures) else lecture
    return redirect("courses:lecture_detail", course_id, target.pk)

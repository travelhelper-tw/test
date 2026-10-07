from django.contrib import admin

from .models import Course, Lecture, Progress


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ["title"]
    search_fields = ["title"]


@admin.register(Lecture)
class LectureAdmin(admin.ModelAdmin):
    list_display = ["order", "chapter_label", "title", "course"]
    list_display_links = ["chapter_label", "title"]
    list_editable = ["order"]
    list_filter = ["course"]
    search_fields = ["chapter_label", "title"]
    ordering = ["course", "order", "pk"]

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(Progress)
class ProgressAdmin(admin.ModelAdmin):
    list_display = ["user", "lecture", "completed"]
    list_filter = ["completed", "lecture__course"]
    list_select_related = ["user", "lecture"]

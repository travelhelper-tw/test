from django.contrib import admin

from .models import Course, Lecture, Progress, Order, Purchase, PaymentNotification


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ["title", "price"]
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


class ReadOnlyPaymentAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Order)
class OrderAdmin(ReadOnlyPaymentAdmin):
    list_display = ["merchant_trade_no", "user", "course_title", "amount", "status", "is_test", "created_at"]
    list_filter = ["status", "is_test"]
    search_fields = ["merchant_trade_no", "gateway_trade_no", "user__username"]
    list_select_related = ["user"]


@admin.register(PaymentNotification)
class PaymentNotificationAdmin(ReadOnlyPaymentAdmin):
    list_display = ["order", "rtn_code", "amount", "simulated", "applied", "received_at"]
    list_select_related = ["order"]


@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = ["user", "course", "active", "is_test", "order", "updated_at"]
    list_filter = ["active", "is_test", "course"]
    list_select_related = ["user", "course", "order"]
    readonly_fields = ["order", "updated_at"]
    actions = ["grant_access", "revoke_access"]

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.action(description="開通選取的課程權限")
    def grant_access(self, request, queryset):
        if request.user.is_superuser:
            for purchase in queryset:
                purchase.active = True
                purchase.save(update_fields=["active", "updated_at"])

    @admin.action(description="撤銷選取的課程權限（不會自動退款）")
    def revoke_access(self, request, queryset):
        if request.user.is_superuser:
            for purchase in queryset:
                purchase.active = False
                purchase.save(update_fields=["active", "updated_at"])

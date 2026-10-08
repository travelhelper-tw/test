from io import StringIO

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse

from .models import Course, Lecture, Progress, Purchase
from .views import lecture_detail


class LectureTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username="reader")
        cls.other_user = get_user_model().objects.create_user(username="other")
        cls.course = Course.objects.create(title="測試課程")
        Purchase.objects.create(user=cls.user, course=cls.course)
        cls.first = Lecture.objects.create(
            course=cls.course, chapter_label="第一章", title="起點", order=10
        )
        cls.second = Lecture.objects.create(
            course=cls.course, chapter_label="第二章", title="練習", order=20
        )
        cls.third = Lecture.objects.create(
            course=cls.course, chapter_label="第三章", title="回顧", order=30
        )
        cls.other_course = Course.objects.create(title="另一門課")
        cls.other_lecture = Lecture.objects.create(
            course=cls.other_course, chapter_label="第一章", title="其他課程", order=1
        )

    def url(self, lecture=None, action="lecture_detail", course=None):
        lecture = lecture or self.first
        return reverse(f"courses:{action}", args=[
            (course or lecture.course).pk, lecture.pk,
        ])

    def test_login_required_for_reading_and_completion(self):
        for action in ["lecture_detail", "complete"]:
            with self.subTest(action=action):
                url = self.url(action=action)
                response = self.client.post(url) if action == "complete" else self.client.get(url)
                self.assertRedirects(
                    response, f"{reverse('login')}?next={url}", fetch_redirect_response=False
                )
        self.assertFalse(Progress.objects.exists())

    def test_percentage_is_scoped_to_course_and_user(self):
        Progress.objects.create(user=self.user, lecture=self.first, completed=True)
        Progress.objects.create(user=self.user, lecture=self.second, completed=False)
        Progress.objects.create(user=self.user, lecture=self.other_lecture, completed=True)
        Progress.objects.create(user=self.other_user, lecture=self.third, completed=True)
        self.client.force_login(self.user)
        response = self.client.get(self.url(self.second))
        self.assertEqual(response.context["percent"], 33)
        self.assertEqual(response.context["done_ids"], {self.first.pk})
        self.assertContains(response, "33% 進度")
        self.assertEqual(response.context["prev"], self.first)
        self.assertEqual(response.context["next"], self.third)

    def test_zero_and_full_progress(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(self.url()).context["percent"], 0)
        Progress.objects.bulk_create([
            Progress(user=self.user, lecture=item, completed=True)
            for item in [self.first, self.second, self.third]
        ])
        self.assertEqual(self.client.get(self.url()).context["percent"], 100)

    def test_no_n_plus_one_queries(self):
        request = RequestFactory().get(self.url())
        request.user = self.user
        with self.assertNumQueries(4):
            response = lecture_detail(request, self.course.pk, self.first.pk)
        self.assertEqual(response.status_code, 200)
        Lecture.objects.bulk_create([
            Lecture(course=self.course, chapter_label=f"章節 {i}", title="佔位", order=i)
            for i in range(40, 70)
        ])
        with self.assertNumQueries(4):
            response = lecture_detail(request, self.course.pk, self.first.pk)
        self.assertEqual(response.status_code, 200)

    def test_complete_redirects_to_next_and_is_idempotent(self):
        self.client.force_login(self.user)
        for _ in range(2):
            response = self.client.post(self.url(action="complete"))
            self.assertRedirects(response, self.url(self.second))
        self.assertEqual(Progress.objects.filter(user=self.user, lecture=self.first).count(), 1)
        self.assertTrue(Progress.objects.get(user=self.user, lecture=self.first).completed)
        self.assertFalse(Progress.objects.filter(user=self.other_user).exists())

    def test_last_lecture_stays_on_same_page(self):
        self.client.force_login(self.user)
        self.assertRedirects(
            self.client.post(self.url(self.third, "complete")), self.url(self.third)
        )

    def test_complete_requires_post_and_csrf(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(self.url(action="complete")).status_code, 405)
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.post(self.url(action="complete")).status_code, 403)
        response = client.get(self.url())
        token = response.cookies["csrftoken"].value
        self.assertRedirects(
            client.post(self.url(action="complete"), {"csrfmiddlewaretoken": token}),
            self.url(self.second),
        )

    def test_lecture_must_belong_to_course(self):
        self.client.force_login(self.user)
        for action in ["lecture_detail", "complete"]:
            url = self.url(self.other_lecture, action, self.course)
            response = self.client.post(url) if action == "complete" else self.client.get(url)
            self.assertEqual(response.status_code, 404)
        self.assertFalse(Progress.objects.exists())

    def test_equal_order_uses_id_as_tiebreaker(self):
        self.second.order = self.first.order
        self.second.save()
        self.client.force_login(self.user)
        response = self.client.get(self.url(self.second))
        self.assertEqual(response.context["prev"], self.first)
        self.assertEqual(response.context["next"], self.third)
        self.assertRedirects(
            self.client.post(self.url(action="complete")), self.url(self.second)
        )

    def test_optional_media_and_trusted_html(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url())
        self.assertNotContains(response, "<audio")
        self.assertNotContains(response, 'class="book-cover"')
        self.first.audio = "audio/demo.mp3"
        self.first.cover = "covers/demo.png"
        self.first.content = "<p><strong>原創簡介</strong></p>"
        self.first.save()
        response = self.client.get(self.url())
        self.assertContains(response, "<audio")
        self.assertContains(response, "/audio/audio/demo.mp3/")
        self.assertNotContains(response, "/media/audio/")
        self.assertContains(response, "/media/covers/demo.png")
        self.assertContains(response, "<strong>原創簡介</strong>")

    def test_home_shows_sales_without_free_lecture_links(self):
        response = self.client.get(reverse("courses:home"))
        self.assertContains(response, reverse("courses:sales", args=[self.course.pk]))
        self.assertNotContains(response, self.url())

    def test_html_editing_restricted_to_superuser(self):
        request = RequestFactory().get("/admin/")
        request.user = self.user
        request.user.is_staff = True
        lecture_admin = admin.site._registry[Lecture]
        self.assertFalse(lecture_admin.has_add_permission(request))
        self.assertFalse(lecture_admin.has_change_permission(request, self.first))
        request.user.is_superuser = True
        self.assertTrue(lecture_admin.has_add_permission(request))
        self.assertTrue(lecture_admin.has_change_permission(request, self.first))

    def test_login_and_post_logout(self):
        self.user.set_password("temporary-test-password")
        self.user.save()
        response = self.client.post(reverse("login"), {
            "username": self.user.username,
            "password": "temporary-test-password",
            "next": self.url(self.second),
        })
        self.assertRedirects(response, self.url(self.second))
        self.assertEqual(self.client.get(reverse("logout")).status_code, 405)
        self.assertRedirects(self.client.post(reverse("logout")), reverse("login"))


class HomeAndDemoTests(TestCase):
    def test_new_demo_course_has_confirmed_price_without_granting_access(self):
        call_command("seed_demo", stdout=StringIO())
        course = Course.objects.get()
        self.assertEqual(course.price, 3680)
        self.assertContains(
            self.client.get(reverse("courses:sales", args=[course.pk])), "NT$ 3680"
        )
        self.assertFalse(Purchase.objects.exists())

    def test_demo_preserves_existing_price_including_disabled_sales(self):
        course = Course.objects.create(title="示範課程：慢讀與聆聽")
        for price in [None, 2400]:
            with self.subTest(price=price):
                course.price = price
                course.save()
                call_command("seed_demo", stdout=StringIO())
                course.refresh_from_db()
                self.assertEqual(course.price, price)

    def test_empty_site(self):
        self.assertContains(self.client.get(reverse("courses:home")), "目前尚無課程")

    def test_course_without_lectures(self):
        Course.objects.create(title="即將推出")
        self.assertContains(self.client.get(reverse("courses:home")), "課程準備中")

    def test_seed_demo_is_repeatable_and_preserves_edits(self):
        call_command("seed_demo", stdout=StringIO())
        lecture = Lecture.objects.first()
        lecture.content = "<p>管理員自己的內容</p>"
        lecture.save()
        call_command("seed_demo", stdout=StringIO())
        self.assertEqual(Course.objects.count(), 1)
        self.assertEqual(Lecture.objects.count(), 3)
        lecture.refresh_from_db()
        self.assertEqual(lecture.content, "<p>管理員自己的內容</p>")
        self.assertFalse(Lecture.objects.exclude(audio="").exists())

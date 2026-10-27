from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.urls import reverse


class PrivateAudioStorage(FileSystemStorage):
    def url(self, name):
        return reverse("courses:audio", kwargs={"name": name})


def private_audio_storage():
    return PrivateAudioStorage(location=settings.PRIVATE_MEDIA_ROOT)

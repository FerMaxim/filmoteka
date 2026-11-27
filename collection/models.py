from django.conf import settings
from django.db import models


class Entry(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    work = models.ForeignKey("catalog.Work", on_delete=models.PROTECT)
    added = models.BooleanField(default=False)
    watched = models.BooleanField(default=False)
    want_to_watch = models.BooleanField(default=False)
    favorite = models.BooleanField(default=False)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "work"], name="entry_owner_work_unique"
            ),
            models.CheckConstraint(
                condition=models.Q(version__gte=1), name="entry_version_positive"
            ),
        ]

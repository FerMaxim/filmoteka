from django.core.validators import MinLengthValidator
from django.db import models


class Work(models.Model):
    class Kind(models.TextChoices):
        FILM = "film", "Фильм"
        SERIES = "series", "Сериал"
        ANIME = "anime", "Аниме"
        ANIMATION = "animation", "Мультфильм"
        OTHER = "other", "Другое"

    title = models.CharField(max_length=300, validators=[MinLengthValidator(1)])
    kind = models.CharField(max_length=16, choices=Kind.choices)

    class Meta:
        ordering = ["title", "pk"]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(title=""), name="work_title_not_empty"
            ),
            models.CheckConstraint(
                condition=models.Q(
                    kind__in=["film", "series", "anime", "animation", "other"]
                ),
                name="work_kind_valid",
            ),
        ]

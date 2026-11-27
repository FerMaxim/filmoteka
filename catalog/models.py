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

    year = models.PositiveSmallIntegerField(null=True, blank=True)
    rating_kinopoisk = models.DecimalField(
        max_digits=3, decimal_places=1, null=True, blank=True
    )
    rating_imdb = models.DecimalField(
        max_digits=3, decimal_places=1, null=True, blank=True
    )
    poster_url = models.URLField(max_length=1000, blank=True)

    class Meta:
        ordering = ["title", "pk"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(year__isnull=True)
                | models.Q(year__gte=1800, year__lte=2200),
                name="work_year_range",
            ),
            models.CheckConstraint(
                condition=models.Q(rating_kinopoisk__isnull=True)
                | models.Q(rating_kinopoisk__gte=0, rating_kinopoisk__lte=10),
                name="work_kp_range",
            ),
            models.CheckConstraint(
                condition=models.Q(rating_imdb__isnull=True)
                | models.Q(rating_imdb__gte=0, rating_imdb__lte=10),
                name="work_imdb_range",
            ),
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


class ExternalRef(models.Model):
    work = models.ForeignKey(
        Work, on_delete=models.CASCADE, related_name="external_refs"
    )
    provider = models.CharField(max_length=40, default="kinopoisk_unofficial")
    external_id = models.CharField(max_length=32)
    fetched_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    source_type = models.CharField(max_length=40, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "external_id"], name="external_ref_identity"
            )
        ]


class SearchCache(models.Model):
    # SHA256 of provider, normalization version, normalized query and page.
    key = models.CharField(max_length=64, primary_key=True)
    payload = models.JSONField(default=dict)
    fetched_at = models.DateTimeField()
    expires_at = models.DateTimeField()


class FetchLease(models.Model):
    key = models.CharField(max_length=80, primary_key=True)
    token = models.UUIDField(null=True)
    expires_at = models.DateTimeField()


class ProviderBudget(models.Model):
    # Digest of the server key: never store the key itself.
    scope = models.CharField(max_length=64, primary_key=True)
    pause_until = models.DateTimeField()
    next_allowed_at = models.DateTimeField()


class ProviderAttempt(models.Model):
    scope = models.CharField(max_length=64, db_index=True)
    created_at = models.DateTimeField(db_index=True)

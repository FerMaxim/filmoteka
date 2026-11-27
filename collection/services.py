from django.db import transaction
from .models import Entry


@transaction.atomic
def add_to_library(*, owner, work):
    entry, _ = Entry.objects.get_or_create(owner=owner, work=work)
    entry = Entry.objects.select_for_update().get(pk=entry.pk)
    if not entry.added:
        entry.added = True
        entry.version += 1
        entry.save(update_fields=["added", "version"])
    return entry


def library_for(owner):
    return (
        Entry.objects.filter(owner=owner, added=True)
        .select_related("work")
        .order_by("work__title", "pk")
    )

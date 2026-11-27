from django.core.management.base import BaseCommand
from catalog.models import Work


class Command(BaseCommand):
    help = "Prepare the minimal synthetic catalog; no external API or accounts."

    def handle(self, *args, **options):
        for title, kind in [
            ("Синтетический маяк", "film"),
            ("Синтетическая орбита", "series"),
            ("Синтетический сад", "anime"),
        ]:
            Work.objects.get_or_create(title=title, kind=kind)
        self.stdout.write("Synthetic catalog ready")

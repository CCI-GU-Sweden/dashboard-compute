from datetime import date, timedelta
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from dashboard_compute.aggregation import ZONE, aggregate


class Command(BaseCommand):
    help = "Rebuild daily interpolated usage for a completed local calendar day."

    def add_arguments(self, parser):
        parser.add_argument("--date", help="YYYY-MM-DD, defaults to previous calendar day")

    def handle(self, *args, **options):
        today = timezone.now().astimezone(ZONE).date()
        try:
            day = date.fromisoformat(options["date"]) if options["date"] else today - timedelta(days=1)
        except ValueError:
            raise CommandError("Invalid date; expected YYYY-MM-DD")
        if day >= today:
            raise CommandError("Only completed calendar days can be aggregated")
        self.stdout.write(f"Aggregated {aggregate(day)} workload rows for {day}")

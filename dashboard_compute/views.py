from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render
from django.utils import timezone
from datetime import date
from decimal import Decimal
import calendar
from accounts.permissions import operational_access
from .models import PodSnapshot, Rate, UsageRecord


@login_required
@user_passes_test(operational_access)
def home(request):
    today = timezone.localdate()
    try:
        year = int(request.GET.get("year", today.year))
        month = int(request.GET.get("month", today.month))
        start = date(year, month, 1)
        if year > 9998:
            raise ValueError("year out of range")
    except (ValueError, OverflowError):
        start = date(today.year, today.month, 1)
    end = date(start.year + (start.month == 12), start.month % 12 + 1, 1)
    records = UsageRecord.objects.filter(ended_at__date__gte=start, ended_at__date__lt=end).order_by("ended_at")
    days = {day: {"day": day, "cpu": Decimal(0), "memory": Decimal(0), "seconds": 0, "costs": {}, "unpriced": 0} for day in range(1, calendar.monthrange(start.year, start.month)[1] + 1)}
    rates = list(Rate.objects.order_by("-effective_from"))
    for record in records:
        item = days[timezone.localtime(record.ended_at).day]
        item["cpu"] += record.cpu_core_hours
        item["memory"] += record.memory_gib_hours
        item["seconds"] += (record.ended_at - record.started_at).total_seconds()
        rate = next((r for r in rates if r.source == record.source and r.effective_from <= record.started_at), None)
        change = any(r.source == record.source and record.started_at < r.effective_from < record.ended_at for r in rates)
        if rate is None or change or (record.disk_gib_hours is not None and rate.disk_per_gib_hour is None):
            item["unpriced"] += 1
            continue
        cost = record.cpu_core_hours * rate.cpu_per_core_hour + record.memory_gib_hours * rate.memory_per_gib_hour
        if record.disk_gib_hours is not None:
            cost += record.disk_gib_hours * rate.disk_per_gib_hour
        item["costs"][rate.currency] = item["costs"].get(rate.currency, Decimal(0)) + cost
    return render(request, "dashboard_compute/home.html", {"days": days.values(), "month": start, "snapshots": PodSnapshot.objects.order_by("-observed_at")[:100]})

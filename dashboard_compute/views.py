import calendar
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import Http404
from django.shortcuts import render
from django.utils import timezone
from accounts.permissions import operational_access

from .aggregation import ZONE, bounds, calculate, workload
from .models import DailyUsage, PodSnapshot, Rate


def day_rows(day):
    today = timezone.now().astimezone(ZONE).date()
    if day == today:
        rows = calculate(day)
    else:
        rows = list(DailyUsage.objects.filter(day=day).values())
    start, end = bounds(day)
    rates = list(Rate.objects.filter(effective_from__lt=end).order_by("-effective_from"))
    for row in rows:
        source = "kubernetes:" + row["namespace"]
        rate = next((r for r in rates if r.source == source and r.effective_from <= start), None)
        changed = any(r.source == source and start < r.effective_from < end for r in rates)
        row["cost"] = None
        row["currency"] = ""
        if rate and not changed:
            row["cost"] = row["cpu_core_hours"] * rate.cpu_per_core_hour + row["memory_gib_hours"] * rate.memory_per_gib_hour
            row["currency"] = rate.currency
    return rows


def latest_workloads():
    cutoff = timezone.now() - timedelta(minutes=5)
    rows = PodSnapshot.objects.filter(observed_at__gte=cutoff).order_by("-observed_at")
    seen = set()
    groups = {}
    for row in rows.iterator():
        identity = (row.namespace, row.pod_uid)
        if identity in seen:
            continue
        seen.add(identity)
        key, name = workload(row)
        group_key = (row.namespace, row.group_id, key)
        item = groups.setdefault(group_key, {"name": name, "group_id": row.group_id, "pods": [], "nodes": set(),
            "observed_at": row.observed_at, "cpu": 0, "memory": 0})
        item["pods"].append(row.pod_name)
        if row.node_name:
            item["nodes"].add(row.node_name)
        item["cpu"] += row.cpu_nanocores
        item["memory"] += row.memory_bytes
        item["observed_at"] = min(item["observed_at"], row.observed_at)
    for item in groups.values():
        item["nodes"] = sorted(item["nodes"])
        item["pods"].sort()
    return sorted(groups.values(), key=lambda item: (item["name"], item["group_id"]))


@login_required
@user_passes_test(operational_access)
def home(request):
    today = timezone.now().astimezone(ZONE).date()
    try:
        year = int(request.GET.get("year", today.year))
        month = int(request.GET.get("month", today.month))
        start = date(year, month, 1)
        if year > 9998:
            raise ValueError()
    except (ValueError, OverflowError):
        start = date(today.year, today.month, 1)
    days = []
    for number in range(1, calendar.monthrange(start.year, start.month)[1] + 1):
        day = date(start.year, start.month, number)
        rows = day_rows(day) if day <= today else []
        groups = {}
        for row in rows:
            item = groups.setdefault(row["group_id"], {"cpu": Decimal(0), "memory": Decimal(0), "seconds": Decimal(0), "costs": {}, "unpriced": 0})
            item["cpu"] += row["cpu_core_hours"]
            item["memory"] += row["memory_gib_hours"]
            item["seconds"] += row["estimated_seconds"]
            if row["cost"] is None:
                item["unpriced"] += 1
            else:
                item["costs"][row["currency"]] = item["costs"].get(row["currency"], Decimal(0)) + row["cost"]
        days.append({"date": day, "groups": groups})
    return render(request, "dashboard_compute/home.html", {"days": days, "month": start, "workloads": latest_workloads()})


@login_required
@user_passes_test(operational_access)
def day_detail(request, day):
    try:
        selected = date.fromisoformat(day)
    except ValueError:
        raise Http404("Invalid date")
    return render(request, "dashboard_compute/day.html", {"day": selected, "rows": day_rows(selected)})

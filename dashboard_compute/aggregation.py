"""Daily, bounded linear interpolation of samples from the same pod instance."""
from collections import defaultdict
from datetime import datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.db import transaction
from .models import DailyUsage, PodSnapshot

ZONE = ZoneInfo("Europe/Stockholm")
MAX_GAP = timedelta(minutes=5)


def bounds(day):
    return (datetime.combine(day, time.min, ZONE), datetime.combine(day + timedelta(days=1), time.min, ZONE))


def workload(row):
    # Jobs and unknown owners always remain isolated by pod UID.
    if not row.job_name and row.workload_kind in {"Deployment", "StatefulSet", "DaemonSet"} and row.workload_name:
        return f"{row.workload_kind}:{row.workload_name}", row.workload_name
    return f"pod:{row.pod_uid}", row.job_name or row.pod_name


def calculate(day):
    start, end = bounds(day)
    samples = PodSnapshot.objects.filter(observed_at__gte=start - MAX_GAP, observed_at__lt=end + MAX_GAP).order_by("namespace", "pod_uid", "observed_at")
    results = {}
    previous = {}
    for row in samples.iterator():
        identity = (row.namespace, row.pod_uid)
        key, name = workload(row)
        group_key = (row.namespace, row.group_id, key)
        if start <= row.observed_at < end:
            entry = results.setdefault(group_key, dict(day=day, namespace=row.namespace, group_id=row.group_id,
                workload_key=key, workload_name=name, job_name=row.job_name, nodes=set(), pod_names=set(),
                sample_count=0, estimated_seconds=Decimal(0), cpu_core_hours=Decimal(0), memory_gib_hours=Decimal(0)))
            entry["sample_count"] += 1
            entry["pod_names"].add(row.pod_name)
            if row.node_name:
                entry["nodes"].add(row.node_name)
        prev = previous.get(identity)
        previous[identity] = row
        if not prev or row.group_id != prev.group_id or workload(prev)[0] != key:
            continue
        duration = (row.observed_at - prev.observed_at).total_seconds()
        if duration <= 0 or duration > MAX_GAP.total_seconds():
            continue
        left, right = max(start, prev.observed_at), min(end, row.observed_at)
        if left >= right:
            continue
        entry = results.setdefault(group_key, dict(day=day, namespace=row.namespace, group_id=row.group_id,
            workload_key=key, workload_name=name, job_name=row.job_name, nodes=set(), pod_names=set(),
            sample_count=0, estimated_seconds=Decimal(0), cpu_core_hours=Decimal(0), memory_gib_hours=Decimal(0)))
        entry["pod_names"].add(row.pod_name)
        if row.node_name:
            entry["nodes"].add(row.node_name)
        seconds = Decimal(str((right - left).total_seconds()))
        total = Decimal(str(duration))
        a = Decimal(str((left - prev.observed_at).total_seconds())) / total
        b = Decimal(str((right - prev.observed_at).total_seconds())) / total
        for field, divisor, dest in (("cpu_nanocores", 10**9, "cpu_core_hours"), ("memory_bytes", 2**30, "memory_gib_hours")):
            before, after = Decimal(getattr(prev, field)), Decimal(getattr(row, field))
            average = before + (after - before) * (a + b) / 2
            entry[dest] += average * seconds / Decimal(divisor * 3600)
        entry["estimated_seconds"] += seconds
    for entry in results.values():
        entry["nodes"] = sorted(entry["nodes"])
        entry["pod_names"] = sorted(entry["pod_names"])
    return list(results.values())


def aggregate(day):
    entries = calculate(day)
    with transaction.atomic():
        DailyUsage.objects.filter(day=day).delete()
        DailyUsage.objects.bulk_create([DailyUsage(**entry) for entry in entries])
    return len(entries)

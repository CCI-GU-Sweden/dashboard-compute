"""Chart data derived from the same bounded interpolation as daily totals."""
from datetime import timedelta, timezone as dt_timezone
from math import ceil

from django.urls import reverse
from .aggregation import MAX_GAP, bounds, workload
from .models import PodSnapshot


def daily_chart(day):
    start, end = bounds(day)
    start, end = start.astimezone(dt_timezone.utc), end.astimezone(dt_timezone.utc)
    count = int((end - start).total_seconds() // 60)
    points = [start + timedelta(minutes=i) for i in range(count)]
    samples = PodSnapshot.objects.filter(observed_at__gte=start - MAX_GAP, observed_at__lt=end + MAX_GAP).order_by("namespace", "pod_uid", "observed_at")
    series = {}
    previous = {}
    unknown = set()
    for row in samples.iterator():
        identity = (row.namespace, row.pod_uid)
        key, name = workload(row)
        group_key = (row.namespace, row.group_id, key)
        prev = previous.get(identity)
        previous[identity] = row
        if not prev or row.group_id != prev.group_id or workload(prev)[0] != key:
            continue
        elapsed = (row.observed_at - prev.observed_at).total_seconds()
        if elapsed <= 0:
            continue
        left = max(0, ceil((prev.observed_at - start).total_seconds() / 60))
        right = min(count, int((row.observed_at - start).total_seconds() // 60) + 1)
        if elapsed > MAX_GAP.total_seconds():
            unknown.update(range(left, right))
            continue
        item = series.setdefault(group_key, {"name": name, "namespace": row.namespace,
            "group": row.group_id, "key": key, "cpu": [None] * count, "memory": [None] * count})
        for i in range(left, right):
            fraction = (points[i] - prev.observed_at).total_seconds() / elapsed
            for field, divisor, target in (("cpu_nanocores", 10**9, "cpu"), ("memory_bytes", 2**30, "memory")):
                value = (getattr(prev, field) + (getattr(row, field) - getattr(prev, field)) * fraction) / divisor
                item[target][i] = (item[target][i] or 0) + value
    # Unknown gaps in any pod make the total incomplete. Do not draw a stack there.
    covered = [i not in unknown and any(item["cpu"][i] is not None for item in series.values()) for i in range(count)]
    for item in series.values():
        for metric in ("cpu", "memory"):
            item[metric] = [((value or 0) if covered[i] else None) for i, value in enumerate(item[metric])]
    return {"times": [point.isoformat() for point in points], "series": list(series.values()), "timezone": "Europe/Stockholm"}


def monthly_chart(day_rows):
    data = []
    for day, rows in day_rows:
        for row in rows:
            data.append({"day": day.isoformat(), "url": reverse("compute_day", args=[day.isoformat()]),
                "name": row["workload_name"], "key": row["workload_key"], "group": row["group_id"],
                "namespace": row["namespace"], "cpu": float(row["cpu_core_hours"]),
                "memory": float(row["memory_gib_hours"]), "cost": float(row["cost"]) if row["cost"] is not None else None,
                "currency": row["currency"]})
    currencies = {row["currency"] for row in data if row["cost"] is not None}
    cost_available = bool(data) and all(row["cost"] is not None for row in data) and len(currencies) == 1
    return {"rows": data, "cost_available": cost_available, "currency": next(iter(currencies)) if cost_available else ""}

import os
from decimal import Decimal
import re

from django.core.management.base import BaseCommand, CommandError
from django.utils.dateparse import parse_datetime
from django.db import transaction
from datetime import timedelta
from kubernetes import client, config
from kubernetes.utils.quantity import parse_quantity

from dashboard_compute.models import PodSnapshot, UsageRecord


def quantity(value, multiplier=1):
    return int(Decimal(parse_quantity(value)) * multiplier)


def window_seconds(value):
    if not re.fullmatch(r"\d+(?:\.\d+)?s", value):
        raise CommandError("Unsupported metrics window: " + value)
    seconds = Decimal(value[:-1])
    if seconds <= 0 or seconds > 60:
        raise CommandError("Metrics window must be between zero and 60 seconds")
    return seconds


class Command(BaseCommand):
    help = "Collect one namespace's pod resource metrics using the in-cluster service account."

    def add_arguments(self, parser):
        parser.add_argument("--namespace", default=os.environ.get("COMPUTE_NAMESPACE"))

    def handle(self, *args, **options):
        namespace = options["namespace"]
        if not namespace:
            raise CommandError("Set COMPUTE_NAMESPACE or pass --namespace")
        config.load_incluster_config()
        core = client.CoreV1Api()
        metrics = client.CustomObjectsApi()
        pods = {p.metadata.name: p for p in core.list_namespaced_pod(namespace).items}
        data = metrics.list_namespaced_custom_object("metrics.k8s.io", "v1beta1", namespace, "pods")
        rows = []
        usage = []
        job_prefix = os.environ.get("COMPUTE_JOB_PREFIX", "metrology-processor-")
        for item in data["items"]:
            pod = pods.get(item["metadata"]["name"])
            if not pod:
                continue
            timestamp = parse_datetime(item["timestamp"])
            if timestamp is None or timestamp.utcoffset() is None:
                raise CommandError("Metrics API returned an invalid timestamp")
            containers = item["containers"]
            owners = pod.metadata.owner_references or []
            job = next((o.name for o in owners if o.kind == "Job"), "")
            if not job.startswith(job_prefix):
                continue
            labels = pod.metadata.labels or {}
            seconds = window_seconds(item.get("window", ""))
            cpu = sum(quantity(c["usage"]["cpu"], 10**9) for c in containers)
            memory = sum(quantity(c["usage"]["memory"]) for c in containers)
            group = labels.get("dashboard.cci.gu.se/omero-group", "CCI") or "CCI"
            rows.append(PodSnapshot(observed_at=timestamp, namespace=namespace,
                pod_uid=pod.metadata.uid, pod_name=pod.metadata.name,
                node_name=pod.spec.node_name or "", job_name=job,
                group_id=group, cpu_nanocores=cpu, memory_bytes=memory,
                window=item.get("window", "")))
            usage.append(UsageRecord(source="kubernetes:" + namespace,
                external_id=pod.metadata.uid + ":" + timestamp.isoformat(), group_id=group,
                started_at=timestamp - timedelta(seconds=float(seconds)), ended_at=timestamp,
                cpu_core_hours=Decimal(cpu) * seconds / Decimal(10**9 * 3600),
                memory_gib_hours=Decimal(memory) * seconds / Decimal(2**30 * 3600)))
        with transaction.atomic():
            PodSnapshot.objects.bulk_create(rows, ignore_conflicts=True)
            UsageRecord.objects.bulk_create(usage, ignore_conflicts=True)
        self.stdout.write(f"Processed {len(rows)} pod snapshots in {namespace}")

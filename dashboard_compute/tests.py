from django.test import SimpleTestCase, TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.core.management import call_command
from .models import UsageRecord, PodSnapshot
from .aggregation import calculate, aggregate, ZONE
from django.core.management.base import CommandError
from .management.commands.collect_compute import quantity, window_seconds


class QuantityTests(SimpleTestCase):
    def test_kubernetes_units(self):
        self.assertEqual(quantity("250m", 10**9), 250000000)
        self.assertEqual(quantity("2Mi"), 2097152)

    def test_window_rejects_unsafe_duration(self):
        self.assertEqual(str(window_seconds("16.298s")), "16.298")
        with self.assertRaises(CommandError):
            window_seconds("61s")


class CollectorTests(TestCase):
    @patch("dashboard_compute.management.commands.collect_compute.client.AppsV1Api")
    @patch("dashboard_compute.management.commands.collect_compute.client.CustomObjectsApi")
    @patch("dashboard_compute.management.commands.collect_compute.client.CoreV1Api")
    @patch("dashboard_compute.management.commands.collect_compute.config.load_incluster_config")
    def test_collection_is_idempotent_and_uses_only_measured_window(self, config, core, metrics, apps):
        apps.return_value.list_namespaced_replica_set.return_value.items = []
        pod = MagicMock()
        pod.metadata.name = "p"
        pod.metadata.uid = "uid"
        pod.metadata.labels = {}
        owner = MagicMock(kind="Job")
        owner.name = "metrology-processor-123"
        owner.controller = True
        pod.metadata.owner_references = [owner]
        pod.spec.node_name = "node"
        core.return_value.list_namespaced_pod.return_value.items = [pod]
        metrics.return_value.list_namespaced_custom_object.return_value = {"items": [{
            "metadata": {"name": "p"}, "timestamp": "2026-11-23T12:00:00Z", "window": "18s",
            "containers": [{"usage": {"cpu": "1", "memory": "1Gi"}}]}]}
        call_command("collect_compute", namespace="test")
        call_command("collect_compute", namespace="test")
        self.assertEqual(PodSnapshot.objects.count(), 1)
        row = UsageRecord.objects.get()
        self.assertEqual(row.cpu_core_hours, Decimal("0.005"))
        self.assertEqual(row.memory_gib_hours, Decimal("0.005"))
        self.assertEqual(row.group_id, "CCI")
        self.assertIsNone(row.disk_gib_hours)

    def test_calendar_access_and_group_display(self):
        now = timezone.now()
        PodSnapshot.objects.create(observed_at=now - timedelta(seconds=10), namespace="test", pod_uid="u",
            pod_name="pod", group_id="CCI", cpu_nanocores=1000000000, memory_bytes=1073741824)
        PodSnapshot.objects.create(observed_at=now, namespace="test", pod_uid="u",
            pod_name="pod", group_id="CCI", cpu_nanocores=1000000000, memory_bytes=1073741824)
        user = get_user_model().objects.create_user(username="staff", role="staff")
        self.client.force_login(user)
        response = self.client.get("/compute/")
        self.assertContains(response, "CCI")
        self.assertContains(response, "Unpriced intervals")
        user.role = "researcher"
        user.save()
        self.assertNotEqual(self.client.get("/compute/").status_code, 200)

    def test_interpolation_preserves_jobs_and_does_not_bridge_gaps(self):
        now = timezone.now().astimezone(ZONE).replace(hour=12, minute=0, second=0, microsecond=0) - timedelta(days=1)
        common = dict(namespace="test", group_id="CCI", cpu_nanocores=1000000000, memory_bytes=1073741824)
        for uid in ("job-a", "job-b"):
            for offset in (0, 60, 600):
                PodSnapshot.objects.create(observed_at=now + timedelta(seconds=offset), pod_uid=uid,
                    pod_name=uid, job_name=uid, workload_kind="Job", workload_name=uid, **common)
        rows = calculate(now.date())
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["estimated_seconds"], Decimal(60))
        self.assertEqual(rows[0]["cpu_core_hours"], Decimal(1) / Decimal(60))
        self.assertEqual(aggregate(now.date()), 2)
        self.assertEqual(aggregate(now.date()), 2)

    def test_deployments_merge_without_interpolating_across_pods(self):
        now = timezone.now().astimezone(ZONE).replace(hour=12, minute=0, second=0, microsecond=0) - timedelta(days=1)
        for uid in ("old", "new"):
            PodSnapshot.objects.create(observed_at=now, namespace="test", pod_uid=uid,
                pod_name=uid, workload_kind="Deployment", workload_name="web", group_id="CCI",
                cpu_nanocores=1000000000, memory_bytes=1073741824)
        rows = calculate(now.date())
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["sample_count"], 2)
        self.assertEqual(rows[0]["estimated_seconds"], 0)

    def test_midnight_is_split_between_days(self):
        midnight = timezone.now().astimezone(ZONE).replace(hour=0, minute=0, second=0, microsecond=0)
        for offset in (-30, 30):
            PodSnapshot.objects.create(observed_at=midnight + timedelta(seconds=offset), namespace="test", pod_uid="u",
                pod_name="p", group_id="CCI", cpu_nanocores=1000000000, memory_bytes=1073741824)
        self.assertEqual(calculate((midnight - timedelta(days=1)).date())[0]["estimated_seconds"], 30)
        self.assertEqual(calculate(midnight.date())[0]["estimated_seconds"], 30)

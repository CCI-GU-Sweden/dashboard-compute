from django.test import SimpleTestCase, TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.core.management import call_command
from .models import UsageRecord, PodSnapshot
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
    @patch("dashboard_compute.management.commands.collect_compute.client.CustomObjectsApi")
    @patch("dashboard_compute.management.commands.collect_compute.client.CoreV1Api")
    @patch("dashboard_compute.management.commands.collect_compute.config.load_incluster_config")
    def test_collection_is_idempotent_and_uses_only_measured_window(self, config, core, metrics):
        pod = MagicMock()
        pod.metadata.name = "p"
        pod.metadata.uid = "uid"
        pod.metadata.labels = {}
        owner = MagicMock(kind="Job")
        owner.name = "metrology-processor-123"
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
        UsageRecord.objects.create(source="csv:example", external_id="one", group_id="CCI",
            started_at=now - timedelta(seconds=10), ended_at=now,
            cpu_core_hours=1, memory_gib_hours=2)
        user = get_user_model().objects.create_user(username="staff", role="staff")
        self.client.force_login(user)
        response = self.client.get("/compute/")
        self.assertContains(response, "CCI")
        self.assertContains(response, "Unpriced intervals")
        user.role = "researcher"
        user.save()
        self.assertNotEqual(self.client.get("/compute/").status_code, 200)

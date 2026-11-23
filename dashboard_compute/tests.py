from django.test import SimpleTestCase
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

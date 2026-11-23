from accounts.permissions import operational_access
from dashboard.modules import DashboardModule

from django.utils import timezone
from .aggregation import ZONE, calculate
from .views import latest_workloads


def overview_metrics(user):
    latest = latest_workloads()
    if not latest:
        return [{"label": "Recent usage", "value": "No samples in the last 5 minutes"}]
    rows = calculate(timezone.now().astimezone(ZONE).date())
    return [
        {"label": "Recent CPU (cores)", "value": f"{sum(r['cpu'] for r in latest) / 10**9:.2f}"},
        {"label": "Recent RAM (GiB)", "value": f"{sum(r['memory'] for r in latest) / 2**30:.2f}"},
        {"label": "Today CPU (core-hours)", "value": f"{sum(r['cpu_core_hours'] for r in rows):.2f}"},
        {"label": "Today RAM (GiB-hours)", "value": f"{sum(r['memory_gib_hours'] for r in rows):.2f}"},
    ]


module = DashboardModule(key="compute", name="Compute", eyebrow="Resources", icon="◈",
    url_name="compute_home", urlconf="dashboard_compute.urls",
    can_view=operational_access, get_metrics=overview_metrics)

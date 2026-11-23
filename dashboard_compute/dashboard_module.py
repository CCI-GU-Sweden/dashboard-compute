from accounts.permissions import operational_access
from dashboard.modules import DashboardModule

from .models import PodSnapshot


def overview_metrics(user):
    latest = PodSnapshot.objects.order_by("-observed_at").first()
    return [{"label": "Latest sample", "value": latest.observed_at.isoformat() if latest else "No data"}]


module = DashboardModule(key="compute", name="Compute", eyebrow="Resources", icon="◈",
    url_name="compute_home", urlconf="dashboard_compute.urls",
    can_view=operational_access, get_metrics=overview_metrics)

from django.db import models


class PodSnapshot(models.Model):
    observed_at = models.DateTimeField(db_index=True)
    namespace = models.CharField(max_length=253)
    pod_uid = models.CharField(max_length=64)
    pod_name = models.CharField(max_length=253)
    node_name = models.CharField(max_length=253, blank=True)
    job_name = models.CharField(max_length=253, blank=True)
    workload_kind = models.CharField(max_length=40, blank=True)
    workload_name = models.CharField(max_length=253, blank=True)
    group_id = models.CharField(max_length=253, default="CCI")
    cpu_nanocores = models.BigIntegerField()
    memory_bytes = models.BigIntegerField()
    disk_bytes = models.BigIntegerField(null=True, blank=True)
    window = models.CharField(max_length=40, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["namespace", "pod_uid", "observed_at"], name="compute_snapshot_identity")]
        indexes = [models.Index(fields=["group_id", "observed_at"], name="compute_group_time")]


class UsageRecord(models.Model):
    """Source-neutral metered interval; quantities are cumulative over the interval."""
    source = models.CharField(max_length=100)
    external_id = models.CharField(max_length=253)
    group_id = models.CharField(max_length=253, default="CCI")
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField(db_index=True)
    cpu_core_hours = models.DecimalField(max_digits=20, decimal_places=9)
    memory_gib_hours = models.DecimalField(max_digits=20, decimal_places=9)
    disk_gib_hours = models.DecimalField(max_digits=20, decimal_places=9, null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["source", "external_id"], name="compute_usage_source_id")]


class Rate(models.Model):
    source = models.CharField(max_length=100)
    currency = models.CharField(max_length=3)
    effective_from = models.DateTimeField()
    cpu_per_core_hour = models.DecimalField(max_digits=12, decimal_places=4)
    memory_per_gib_hour = models.DecimalField(max_digits=12, decimal_places=4)
    disk_per_gib_hour = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["source", "effective_from"], name="compute_rate_effective")]


class DailyUsage(models.Model):
    day = models.DateField(db_index=True)
    namespace = models.CharField(max_length=253)
    group_id = models.CharField(max_length=253)
    workload_key = models.CharField(max_length=320)
    workload_name = models.CharField(max_length=253)
    job_name = models.CharField(max_length=253, blank=True)
    nodes = models.JSONField(default=list)
    pod_names = models.JSONField(default=list)
    sample_count = models.PositiveIntegerField(default=0)
    estimated_seconds = models.DecimalField(max_digits=20, decimal_places=3, default=0)
    cpu_core_hours = models.DecimalField(max_digits=20, decimal_places=9, default=0)
    memory_gib_hours = models.DecimalField(max_digits=20, decimal_places=9, default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["day", "namespace", "group_id", "workload_key"], name="compute_daily_identity")]

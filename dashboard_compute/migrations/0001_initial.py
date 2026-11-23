from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(
            name="PodSnapshot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("observed_at", models.DateTimeField(db_index=True)),
                ("namespace", models.CharField(max_length=253)),
                ("pod_uid", models.CharField(max_length=64)),
                ("pod_name", models.CharField(max_length=253)),
                ("node_name", models.CharField(blank=True, max_length=253)),
                ("job_name", models.CharField(blank=True, max_length=253)),
                ("group_id", models.CharField(default="CCI", max_length=253)),
                ("cpu_nanocores", models.BigIntegerField()),
                ("memory_bytes", models.BigIntegerField()),
                ("window", models.CharField(blank=True, max_length=40)),
            ],
            options={"indexes": [models.Index(fields=["group_id", "observed_at"], name="compute_group_time")], "constraints": [models.UniqueConstraint(fields=("namespace", "pod_uid", "observed_at"), name="compute_snapshot_identity")]},
        ),
    ]

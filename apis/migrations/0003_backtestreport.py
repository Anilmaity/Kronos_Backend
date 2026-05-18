# Generated for BacktestReport model.
# NOTE: The underlying `apis_backtestreport` table was created out-of-band via
# raw SQL on 2026-05-18 (from KronosStrategies). To bring this migration in
# sync with the existing DB, run:
#     python manage.py migrate apis 0003_backtestreport --fake
# Fresh deploys will pick this up normally and CREATE TABLE.
#
# Schema mirrors strategies/shared/models.py::BacktestReport (SQLAlchemy).

import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('apis', '0002_alter_action_trigger_type_alter_userbroker_api_key'),
    ]

    operations = [
        migrations.CreateModel(
            name='BacktestReport',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False, unique=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('modified_at', models.DateTimeField(auto_now=True)),
                ('run_label', models.CharField(max_length=200)),
                ('period_start', models.DateField(blank=True, null=True)),
                ('period_end', models.DateField(blank=True, null=True)),
                ('trades', models.IntegerField(default=0)),
                ('wins', models.IntegerField(default=0)),
                ('losses', models.IntegerField(default=0)),
                ('win_rate_pct', models.DecimalField(blank=True, decimal_places=4, max_digits=8, null=True)),
                ('pnl_pts', models.DecimalField(blank=True, decimal_places=4, max_digits=18, null=True)),
                ('max_dd_pts', models.DecimalField(blank=True, decimal_places=4, max_digits=18, null=True)),
                ('avg_win_pts', models.DecimalField(blank=True, decimal_places=4, max_digits=18, null=True)),
                ('avg_loss_pts', models.DecimalField(blank=True, decimal_places=4, max_digits=18, null=True)),
                ('profit_factor', models.DecimalField(blank=True, decimal_places=4, max_digits=12, null=True)),
                ('expectancy_pts', models.DecimalField(blank=True, decimal_places=6, max_digits=18, null=True)),
                ('sharpe_daily', models.DecimalField(blank=True, decimal_places=4, max_digits=12, null=True)),
                ('source_csv', models.CharField(blank=True, default='', max_length=500)),
                ('params_snapshot', models.JSONField(blank=True, default=dict)),
                ('notes', models.TextField(blank=True, default='')),
                ('strategy', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='backtest_reports', to='apis.strategy')),
            ],
            options={
                'indexes': [
                    models.Index(fields=['strategy'], name='apis_backte_strateg_idx'),
                    models.Index(fields=['run_label'], name='apis_backte_run_lab_idx'),
                ],
            },
        ),
    ]

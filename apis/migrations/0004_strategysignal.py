# Generated for StrategySignal model.
# The underlying apis_strategysignal table was created out-of-band via raw
# SQL on 2026-05-18. To bring this migration in sync with the existing DB:
#     python manage.py migrate apis 0004_strategysignal --fake
# Fresh deploys will pick this up normally and CREATE TABLE.

import uuid
from django.db import migrations, models
from django.utils import timezone


class Migration(migrations.Migration):

    dependencies = [
        ('apis', '0003_backtestreport'),
    ]

    operations = [
        migrations.CreateModel(
            name='StrategySignal',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False, unique=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('modified_at', models.DateTimeField(auto_now=True)),
                ('symbol', models.CharField(max_length=50)),
                ('side', models.CharField(max_length=10)),
                ('entry_price', models.DecimalField(decimal_places=5, max_digits=25)),
                ('stop_loss', models.DecimalField(blank=True, decimal_places=5, max_digits=25, null=True)),
                ('take_profit', models.DecimalField(blank=True, decimal_places=5, max_digits=25, null=True)),
                ('reason', models.CharField(blank=True, default='', max_length=500)),
                ('status', models.CharField(choices=[('FIRED', 'FIRED'), ('PLACED', 'PLACED'), ('REJECTED', 'REJECTED')], default='FIRED', max_length=30)),
                ('rejection_reason', models.CharField(blank=True, default='', max_length=500)),
                ('signal_at', models.DateTimeField(default=timezone.now)),
                ('strategy', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='strategy_signals', to='apis.strategy')),
                ('position', models.ForeignKey(blank=True, null=True, on_delete=models.deletion.SET_NULL, related_name='strategy_signals', to='apis.position')),
            ],
            options={
                'indexes': [
                    models.Index(fields=['strategy'], name='apis_strats_strateg_idx'),
                    models.Index(fields=['signal_at'], name='apis_strats_signal__idx'),
                    models.Index(fields=['status'], name='apis_strats_status_idx'),
                ],
            },
        ),
    ]

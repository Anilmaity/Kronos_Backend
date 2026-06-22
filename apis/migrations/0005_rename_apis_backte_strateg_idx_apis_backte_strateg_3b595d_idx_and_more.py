# Accounts feature — add MetaAPI credential fields to UserBroker.
# Hand-trimmed to ONLY the additive UserBroker columns. Django's auto-generated
# version bundled unrelated drifted operations (index renames, id/choices
# AlterFields, and a broken api_key default) that must NOT be applied to the
# production DB. Those cosmetic changes remain pending and can be regenerated
# into a later migration if ever needed.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('apis', '0004_strategysignal'),
    ]

    operations = [
        migrations.AddField(
            model_name='userbroker',
            name='label',
            field=models.CharField(default='', max_length=120),
        ),
        migrations.AddField(
            model_name='userbroker',
            name='meta_account_id',
            field=models.CharField(default='', max_length=120),
        ),
        migrations.AddField(
            model_name='userbroker',
            name='meta_api_token_enc',
            field=models.TextField(default=''),
        ),
        migrations.AddField(
            model_name='userbroker',
            name='meta_api_token_last4',
            field=models.CharField(default='', max_length=4),
        ),
    ]

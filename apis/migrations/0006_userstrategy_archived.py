from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("apis", "0005_rename_apis_backte_strateg_idx_apis_backte_strateg_3b595d_idx_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="userstrategy",
            name="archived",
            field=models.BooleanField(default=False),
        ),
    ]

from django.apps.registry import apps
from django.contrib import admin

# Register your models here.
from Kronos_Backend.utils.custom_admin import CustomModelAdmin

app = apps.get_app_config("apis")

for model_name, model in app.models.items():
    try:
        # admin_class = type('AdminClass', (CustomModelAdmin, admin.ModelAdmin), {})
        admin.site.register(model, CustomModelAdmin)
    except admin.sites.AlreadyRegistered:
        pass

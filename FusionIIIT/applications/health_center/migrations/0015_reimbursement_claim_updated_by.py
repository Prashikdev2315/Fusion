from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('health_center', '0014_phc_staff_module'),
    ]

    operations = [
        migrations.AddField(
            model_name='phcreimbursementclaim',
            name='updated_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='phc_reimbursement_claims_updated',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]

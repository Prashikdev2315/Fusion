# Generated migration for BR-08 and BR-06 enforcement

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('health_center', '0019_auto_20260413_1722'),
    ]

    operations = [
        migrations.AddField(
            model_name='phcreimbursementclaim',
            name='requires_professor_approval',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='phcreimbursementclaim',
            name='professor_approved_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='professor_reimbursement_approvals', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='phcreimbursementclaim',
            name='status',
            field=models.CharField(
                choices=[
                    ('submitted', 'submitted'),
                    ('pending_phc_review', 'pending_phc_review'),
                    ('pending_professor_approval', 'pending_professor_approval'),
                    ('pending_accounts_verification', 'pending_accounts_verification'),
                    ('approved', 'approved'),
                    ('rejected', 'rejected'),
                    ('reimbursed', 'reimbursed'),
                ],
                default='submitted',
                max_length=40
            ),
        ),
    ]

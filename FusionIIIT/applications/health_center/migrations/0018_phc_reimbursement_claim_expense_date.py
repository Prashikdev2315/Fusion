from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('health_center', '0017_phc_reimbursement_document'),
    ]

    operations = [
        migrations.AddField(
            model_name='phcreimbursementclaim',
            name='expense_date',
            field=models.DateField(blank=True, null=True),
        ),
    ]

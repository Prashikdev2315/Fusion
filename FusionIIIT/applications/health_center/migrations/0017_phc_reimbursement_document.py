from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('health_center', '0016_merge_reimbursement_updated_by'),
    ]

    operations = [
        migrations.CreateModel(
            name='PHCReimbursementDocument',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file', models.FileField(upload_to='health_center/reimbursement_documents/%Y/%m/%d/')),
                ('original_name', models.CharField(max_length=255)),
                ('uploaded_at', models.DateTimeField(auto_now_add=True)),
                ('claim', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='documents', to='health_center.PHCReimbursementClaim')),
                ('uploaded_by', models.ForeignKey(null=True, on_delete=models.deletion.SET_NULL, related_name='phc_reimbursement_documents_uploaded', to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]

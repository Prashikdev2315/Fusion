# Generated migration for PHC Staff Module

from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('health_center', '0013_reimbursement_features'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # DoctorAttendance model
        migrations.CreateModel(
            name='DoctorAttendance',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('available', 'Available'), ('departed', 'Departed'), ('on_leave', 'On Leave')], max_length=20)),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('doctor', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='attendance_logs', to='health_center.Doctor')),
                ('marked_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='marked_attendance', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-timestamp'],
            },
        ),

        # Inventory model
        migrations.CreateModel(
            name='Inventory',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('stock_quantity', models.IntegerField(default=0)),
                ('reorder_threshold', models.IntegerField(default=10)),
                ('last_updated', models.DateTimeField(auto_now=True)),
                ('last_updated_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ('medicine', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='inventory', to='health_center.All_Medicine')),
            ],
        ),

        # InventoryTransaction model
        migrations.CreateModel(
            name='InventoryTransaction',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('transaction_type', models.CharField(choices=[('add', 'Stock Added'), ('deduct', 'Stock Deducted'), ('adjust', 'Adjustment')], max_length=20)),
                ('quantity_change', models.IntegerField()),
                ('reason', models.CharField(blank=True, max_length=200)),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('inventory', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='transactions', to='health_center.Inventory')),
                ('performed_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='inventory_transactions', to=settings.AUTH_USER_MODEL)),
            ],
        ),

        # LowStockAlert model
        migrations.CreateModel(
            name='LowStockAlert',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('current_stock', models.IntegerField()),
                ('threshold', models.IntegerField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('acknowledged', models.BooleanField(default=False)),
                ('acknowledged_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ('inventory', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='alerts', to='health_center.Inventory')),
            ],
        ),

        # Requisition model
        migrations.CreateModel(
            name='Requisition',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('submitted', 'Submitted'), ('approved', 'Approved'), ('rejected', 'Rejected'), ('fulfilled', 'Fulfilled'), ('closed', 'Closed')], default='submitted', max_length=20)),
                ('reason', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('fulfilled_at', models.DateTimeField(blank=True, null=True)),
                ('approved_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='requisitions_approved', to=settings.AUTH_USER_MODEL)),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='requisitions_created', to=settings.AUTH_USER_MODEL)),
                ('fulfilled_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='requisitions_fulfilled', to=settings.AUTH_USER_MODEL)),
            ],
        ),

        # RequisitionItem model
        migrations.CreateModel(
            name='RequisitionItem',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity_requested', models.IntegerField()),
                ('quantity_fulfilled', models.IntegerField(default=0)),
                ('priority', models.CharField(choices=[('urgent', 'Urgent'), ('normal', 'Normal')], default='normal', max_length=20)),
                ('medicine', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='health_center.All_Medicine')),
                ('requisition', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items_list', to='health_center.Requisition')),
            ],
        ),

        # Requisition ManyToMany
        migrations.AddField(
            model_name='requisition',
            name='items',
            field=models.ManyToManyField(related_name='requisitions', through='health_center.RequisitionItem', to='health_center.All_Medicine'),
        ),

        # AmbulanceLog model
        migrations.CreateModel(
            name='AmbulanceLog',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('patient_name', models.CharField(max_length=100)),
                ('pickup_location', models.CharField(max_length=200)),
                ('destination', models.CharField(max_length=200)),
                ('status', models.CharField(choices=[('requested', 'Requested'), ('in_transit', 'In Transit'), ('arrived', 'Arrived'), ('completed', 'Completed'), ('cancelled', 'Cancelled')], max_length=20)),
                ('requested_at', models.DateTimeField(auto_now_add=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('notes', models.TextField(blank=True)),
                ('log_created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='ambulance_logs', to=settings.AUTH_USER_MODEL)),
            ],
        ),

        # Announcement model
        migrations.CreateModel(
            name='Announcement',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200)),
                ('content', models.TextField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('published', models.BooleanField(default=True)),
                ('expires_at', models.DateTimeField(blank=True, null=True)),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='announcements_created', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),

        # PatientSearch model (for optimization)
        migrations.CreateModel(
            name='PatientSearch',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('searchable_name', models.CharField(db_index=True, max_length=200)),
                ('search_updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='phc_patient_search', to=settings.AUTH_USER_MODEL)),
            ],
        ),

        # ReimbursementProcessingLog model
        migrations.CreateModel(
            name='ReimbursementProcessingLog',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action', models.CharField(choices=[('viewed', 'Viewed'), ('forwarded', 'Forwarded'), ('returned', 'Returned'), ('rejected', 'Rejected')], max_length=20)),
                ('notes', models.TextField(blank=True)),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('claim', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='processing_logs', to='health_center.PHCReimbursementClaim')),
                ('performed_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reimbursement_actions', to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]

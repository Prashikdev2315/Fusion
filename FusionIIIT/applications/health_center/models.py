
from django.db import models
from datetime import date
from django.contrib.auth.models import User

from applications.globals.models import ExtraInfo
from applications.hr2.models import EmpDependents

# Create your models here.

class Constants:
    DAYS_OF_WEEK = (
        (0, 'Monday'),
        (1, 'Tuesday'),
        (2, 'Wednesday'),
        (3, 'Thursday'),
        (4, 'Friday'),
        (5, 'Saturday'),
        (6, 'Sunday')
    )
    
    NAME_OF_DOCTOR = (
        (0, 'Dr.Sharma'),
        (1, 'Dr.Vinay'),

    )
    
    NAME_OF_PATHOLOGIST = (
        (0, 'Dr.Ajay'),
        (1, 'Dr.Rahul'),

    )

class Doctor(models.Model):
    doctor_name = models.CharField(max_length=50)
    doctor_phone = models.CharField(max_length=15)
    specialization = models.CharField(max_length=100)
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.doctor_name

class Pathologist(models.Model):
    pathologist_name = models.CharField(max_length=50)
    pathologist_phone = models.CharField(max_length=15)
    specialization = models.CharField(max_length=100)
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.pathologist_name

# class Complaint(models.Model):
#     user_id = models.ForeignKey(ExtraInfo,on_delete=models.CASCADE)
#     feedback = models.CharField(max_length=100, null=True, blank=False)                          #This is the feedback given by the compounder
#     complaint = models.CharField(max_length=100, null=True, blank=False)                         #Here Complaint given by user cannot be NULL!
#     date = models.DateField(auto_now=True)

class All_Medicine(models.Model):
    medicine_name = models.CharField(max_length=1000,default="NOT_SET", null=True)
    brand_name = models.CharField(max_length=1000,default="NOT_SET", null=True)
    constituents = models.TextField(default="NOT_SET",  null=True)
    manufacturer_name = models.CharField(max_length=1000,default="NOT_SET", null=True)
    threshold = models.IntegerField(default=0, null=True)
    pack_size_label = models.CharField(max_length=1000,default="NOT_SET", null=True)

    def __str__(self):
        return self.brand_name
    
class Stock_entry(models.Model):
    medicine_id = models.ForeignKey(All_Medicine, on_delete=models.CASCADE)
    quantity = models.IntegerField(default=0)
    supplier = models.CharField(max_length=50,default="NOT_SET")
    Expiry_date = models.DateField()
    date = models.DateField(auto_now=True)
    # generic_name = models.CharField(max_length=80)

    def __str__(self):
        return self.medicine_id.medicine_name
    

class Required_medicine(models.Model):
    medicine_id = models.ForeignKey(All_Medicine,on_delete = models.CASCADE)
    quantity = models.IntegerField()
    threshold = models.IntegerField()

class Present_Stock(models.Model):
    quantity = models.IntegerField(default=0)
    stock_id = models.ForeignKey(Stock_entry,on_delete=models.CASCADE)
    medicine_id = models.ForeignKey(All_Medicine, on_delete=models.CASCADE)
    Expiry_date =models.DateField()


    # generic_name = models.CharField(max_length=80)

    def __str__(self):
        return str(self.Expiry_date)

class Doctors_Schedule(models.Model):
    doctor_id = models.ForeignKey(Doctor,on_delete=models.CASCADE)
    # pathologist_id = models.ForeignKey(Pathologist,on_delete=models.CASCADE, default=0)
    day = models.CharField(choices=Constants.DAYS_OF_WEEK, max_length=10)
    from_time = models.TimeField(null=True,blank=True)  
    to_time = models.TimeField(null=True,blank=True)
    room = models.IntegerField()
    date = models.DateField(auto_now=True)
    
class Pathologist_Schedule(models.Model):
    # doctor_id = models.ForeignKey(Doctor,on_delete=models.CASCADE)
    pathologist_id = models.ForeignKey(Pathologist,on_delete=models.CASCADE)
    day = models.CharField(choices=Constants.DAYS_OF_WEEK, max_length=10)
    from_time = models.TimeField(null=True,blank=True)
    to_time = models.TimeField(null=True,blank=True)
    room = models.IntegerField()
    date = models.DateField(auto_now=True)

class All_Prescription(models.Model):
    user_id = models.CharField(max_length=15)
    doctor_id = models.ForeignKey(Doctor, on_delete=models.CASCADE,null=True, blank=True)
    details = models.TextField(null=True)
    date = models.DateField()
    suggestions = models.TextField(null=True)
    test = models.CharField(max_length=200, null=True, blank=True)
    file_id=models.IntegerField(default=0)
    is_dependent = models.BooleanField(default=False)
    dependent_name = models.CharField(max_length=30,default="SELF")
    dependent_relation = models.CharField(max_length=20,default="SELF")
    # appointment = models.ForeignKey(Appointment, on_delete=models.CASCADE,null=True, blank=True)

    def __str__(self):
        return self.user_id

class Prescription_followup(models.Model):
    prescription_id=models.ForeignKey(All_Prescription,on_delete=models.CASCADE)
    details = models.TextField(null=True)
    date = models.DateField()
    test = models.CharField(max_length=200, null=True, blank=True)
    suggestions = models.TextField(null=True)
    Doctor_id = models.ForeignKey(Doctor,on_delete=models.CASCADE, null=True, blank=True)
    file_id=models.IntegerField(default=0)
class All_Prescribed_medicine(models.Model):
    prescription_id = models.ForeignKey(All_Prescription,on_delete=models.CASCADE)
    medicine_id = models.ForeignKey(All_Medicine,on_delete=models.CASCADE)
    stock = models.ForeignKey(Present_Stock,on_delete=models.CASCADE,null=True)
    prescription_followup_id = models.ForeignKey(Prescription_followup,on_delete=models.CASCADE,null=True)
    quantity = models.IntegerField(default=0)
    days = models.IntegerField(default=0)
    times = models.IntegerField(default=0)
    revoked = models.BooleanField(default=False)
    revoked_date = models.DateField(null=True)
    revoked_prescription = models.ForeignKey(Prescription_followup,on_delete=models.CASCADE,null=True,related_name="revoked_priscription")

    def __str__(self):
        return self.medicine_id.medicine_name
class Required_tabel_last_updated(models.Model):
    date=models.DateField()
class files(models.Model):
    file_data = models.BinaryField()

class medical_relief(models.Model):
    description = models.CharField(max_length=200)
    file = models.FileField(upload_to='medical_files/') 
    file_id=models.IntegerField(default=0)
    compounder_forward_flag = models.BooleanField(default=False)
    acc_admin_forward_flag = models.BooleanField(default=False)
    
    
class MedicalProfile(models.Model):
    user_id = models.ForeignKey(ExtraInfo, on_delete=models.CASCADE, null=True) 
    date_of_birth = models.DateField()
    gender_choices = [
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
    ]
    gender = models.CharField(max_length=1, choices=gender_choices)
    blood_type_choices = [
        ('A+', 'A+'),
        ('A-', 'A-'),
        ('B+', 'B+'),
        ('B-', 'B-'),
        ('AB+', 'AB+'),
        ('AB-', 'AB-'),
        ('O+', 'O+'),
        ('O-', 'O-'),
    ]
    blood_type = models.CharField(max_length=3, choices=blood_type_choices)
    height = models.DecimalField(max_digits=5, decimal_places=2)  
    weight = models.DecimalField(max_digits=5, decimal_places=2)  


class PHCUserRoleProfile(models.Model):
    ROLE_CHOICES = (
        ('student', 'student'),
        ('professor', 'professor'),
        ('phc_staff', 'phc_staff'),
        ('accounts', 'accounts'),
        ('authority', 'authority'),
    )

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='phc_role_profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)

    def __str__(self):
        return '{} - {}'.format(self.user.username, self.role)


class StudentProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='phc_student_profile')
    registration_id = models.CharField(max_length=30, unique=True)
    course = models.CharField(max_length=100, null=True, blank=True)
    year = models.PositiveSmallIntegerField(null=True, blank=True)

    def __str__(self):
        return '{} - {}'.format(self.user.username, self.registration_id)


class StaffProfile(models.Model):
    ROLE_TYPE_CHOICES = (
        ('professor', 'professor'),
        ('phc_staff', 'phc_staff'),
        ('accounts', 'accounts'),
        ('authority', 'authority'),
    )

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='phc_staff_profile')
    employee_id = models.CharField(max_length=30, unique=True)
    designation = models.CharField(max_length=100, null=True, blank=True)
    role_type = models.CharField(max_length=20, choices=ROLE_TYPE_CHOICES)
    approval_level = models.CharField(max_length=50, null=True, blank=True)

    def __str__(self):
        return '{} - {}'.format(self.user.username, self.employee_id)


class PHCUserAuditLog(models.Model):
    action = models.CharField(max_length=50)
    performed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='phc_user_audit_performed',
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    created_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='phc_user_audit_created',
    )

    def __str__(self):
        return '{} by {} for {}'.format(self.action, self.performed_by, self.created_user)


class Appointment(models.Model):
    STATUS_CHOICES = (
        ('booked', 'booked'),
        ('completed', 'completed'),
        ('cancelled', 'cancelled'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='phc_appointments')
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name='phc_appointments')
    date = models.DateField()
    time_slot = models.TimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='booked')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [['doctor', 'date', 'time_slot']]


class Visit(models.Model):
    appointment = models.OneToOneField(Appointment, on_delete=models.CASCADE, related_name='visit', null=True, blank=True)
    patient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='phc_visits_as_patient')
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name='phc_visits', null=True, blank=True)
    diagnosis = models.TextField()
    prescription = models.TextField()
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='phc_visits_created')
    created_at = models.DateTimeField(auto_now_add=True)


class PHCAppointmentAuditLog(models.Model):
    action = models.CharField(max_length=50)
    performed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='phc_appointment_audit_performed',
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    appointment = models.ForeignKey(
        Appointment,
        on_delete=models.CASCADE,
        related_name='audit_logs',
        null=True,
        blank=True,
    )
    visit = models.ForeignKey(
        Visit,
        on_delete=models.CASCADE,
        related_name='audit_logs',
        null=True,
        blank=True,
    )
    metadata = models.TextField(blank=True, default='')


class PHCReimbursementClaim(models.Model):
    STATUS_CHOICES = (
        ('submitted', 'submitted'),
        ('pending_phc_review', 'pending_phc_review'),
        ('pending_professor_approval', 'pending_professor_approval'),
        ('pending_accounts_verification', 'pending_accounts_verification'),
        ('approved', 'approved'),
        ('rejected', 'rejected'),
        ('reimbursed', 'reimbursed'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='phc_reimbursement_claims')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    reason = models.TextField()
    expense_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=40, choices=STATUS_CHOICES, default='submitted')
    requires_professor_approval = models.BooleanField(default=False)  # BR-08: Flag for high-value claims
    professor_approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='professor_reimbursement_approvals',
    )
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='phc_reimbursement_claims_updated',
    )
    created_at = models.DateTimeField(auto_now_add=True)


class PHCReimbursementDocument(models.Model):
    claim = models.ForeignKey(
        PHCReimbursementClaim,
        on_delete=models.CASCADE,
        related_name='documents',
    )
    file = models.FileField(upload_to='health_center/reimbursement_documents/%Y/%m/%d/')
    original_name = models.CharField(max_length=255)
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='phc_reimbursement_documents_uploaded',
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)


class PHCReimbursementAuditLog(models.Model):
    action = models.CharField(max_length=50)
    performed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='phc_reimbursement_audit_performed',
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    claim = models.ForeignKey(
        PHCReimbursementClaim,
        on_delete=models.CASCADE,
        related_name='audit_logs',
    )
    metadata = models.TextField(blank=True, default='')


# ===========================
# PHC STAFF MODULE MODELS
# ===========================

class DoctorAttendance(models.Model):
    """Track doctor check-in/check-out (UC-08)"""
    ATTENDANCE_CHOICES = (
        ('available', 'Available'),
        ('departed', 'Departed'),
        ('on_leave', 'On Leave'),
    )
    
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name='attendance_logs')
    status = models.CharField(max_length=20, choices=ATTENDANCE_CHOICES)
    timestamp = models.DateTimeField(auto_now_add=True)
    marked_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='marked_attendance')
    
    class Meta:
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.doctor.doctor_name} - {self.status} at {self.timestamp}"


class Inventory(models.Model):
    """Enhanced inventory tracking (UC-09)"""
    medicine = models.OneToOneField(All_Medicine, on_delete=models.CASCADE, related_name='inventory')
    stock_quantity = models.IntegerField(default=0)
    reorder_threshold = models.IntegerField(default=10)
    last_updated = models.DateTimeField(auto_now=True)
    last_updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    def is_low_stock(self):
        return self.stock_quantity <= self.reorder_threshold
    
    def __str__(self):
        return f"{self.medicine.medicine_name} - {self.stock_quantity} units"


class InventoryTransaction(models.Model):
    """Log of all inventory changes (BR-09 Audit)"""
    TRANSACTION_TYPE_CHOICES = (
        ('add', 'Stock Added'),
        ('deduct', 'Stock Deducted'),
        ('adjust', 'Adjustment'),
    )
    
    inventory = models.ForeignKey(Inventory, on_delete=models.CASCADE, related_name='transactions')
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPE_CHOICES)
    quantity_change = models.IntegerField()
    reason = models.CharField(max_length=200, blank=True)
    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='inventory_transactions')
    timestamp = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.transaction_type} - {self.quantity_change} units on {self.timestamp}"


class LowStockAlert(models.Model):
    """Triggered when inventory below threshold (BR-07)"""
    inventory = models.ForeignKey(Inventory, on_delete=models.CASCADE, related_name='alerts')
    current_stock = models.IntegerField()
    threshold = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    acknowledged = models.BooleanField(default=False)
    acknowledged_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    def __str__(self):
        return f"Low stock alert for {self.inventory.medicine.medicine_name}"


class Requisition(models.Model):
    """Medicine requisition request (UC-10, UC-14)"""
    STATUS_CHOICES = (
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('fulfilled', 'Fulfilled'),
        ('closed', 'Closed'),
    )
    
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='requisitions_created')
    items = models.ManyToManyField(All_Medicine, through='RequisitionItem')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='submitted')
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='requisitions_approved')
    fulfilled_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='requisitions_fulfilled')
    fulfilled_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"Requisition #{self.id} - {self.status}"


class RequisitionItem(models.Model):
    """Items in a requisition"""
    requisition = models.ForeignKey(Requisition, on_delete=models.CASCADE, related_name='items_list')
    medicine = models.ForeignKey(All_Medicine, on_delete=models.CASCADE)
    quantity_requested = models.IntegerField()
    quantity_fulfilled = models.IntegerField(default=0)
    priority = models.CharField(max_length=20, choices=(('urgent', 'Urgent'), ('normal', 'Normal')), default='normal')
    
    def __str__(self):
        return f"{self.medicine.medicine_name} - {self.quantity_requested} units"


class AmbulanceLog(models.Model):
    """Ambulance usage tracking (UC-11)"""
    STATUS_CHOICES = (
        ('requested', 'Requested'),
        ('in_transit', 'In Transit'),
        ('arrived', 'Arrived'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    )
    
    patient_name = models.CharField(max_length=100)
    pickup_location = models.CharField(max_length=200)
    destination = models.CharField(max_length=200)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    requested_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    log_created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='ambulance_logs')
    notes = models.TextField(blank=True)
    
    def __str__(self):
        return f"Ambulance - {self.patient_name} to {self.destination}"


class Announcement(models.Model):
    """PHC announcements/messages (UC-12)"""
    title = models.CharField(max_length=200)
    content = models.TextField()
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='announcements_created')
    created_at = models.DateTimeField(auto_now_add=True)
    published = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return self.title


class PatientSearch(models.Model):
    """Helper for patient lookups (search optimization)"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='phc_patient_search')
    searchable_name = models.CharField(max_length=200, db_index=True)
    search_updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.searchable_name


class ReimbursementProcessingLog(models.Model):
    """Track reimbursement claim processing (UC-15)"""
    ACTION_CHOICES = (
        ('viewed', 'Viewed'),
        ('forwarded', 'Forwarded'),
        ('returned', 'Returned'),
        ('rejected', 'Rejected'),
    )
    
    claim = models.ForeignKey(PHCReimbursementClaim, on_delete=models.CASCADE, related_name='processing_logs')
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='reimbursement_actions')
    notes = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.action} by {self.performed_by} on claim #{self.claim.id}"




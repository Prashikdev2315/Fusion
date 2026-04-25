"""
PHC Staff (Compounder) Services
Implements UC-06 through UC-15 use cases with strict RBAC and audit logging
"""

import datetime
import json
from django.db import transaction, DatabaseError, IntegrityError
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models import Sum, Q

from .models import (
    Appointment, Visit, Doctor, Doctors_Schedule, MedicalProfile,
    All_Medicine, Inventory, InventoryTransaction, LowStockAlert,
    Requisition, RequisitionItem, AmbulanceLog, Announcement,
    DoctorAttendance, PHCAppointmentAuditLog, PatientSearch,
    Doctors_Schedule, PHCReimbursementClaim, PHCReimbursementAuditLog,
    ReimbursementProcessingLog,
)
from .role_guards import resolve_phc_role, ROLE_PHC_STAFF


class PHCStaffError(Exception):
    """Base exception for PHC staff operations"""
    pass


class PHCStaffPermissionError(PHCStaffError):
    """Raised when user lacks required permissions"""
    pass


# ===========================
# UC-06: PATIENT RECORD SYSTEM
# ===========================

def searchPatientService(search_query, request_user):
    """
    Search patients by ID, username, or full name
    BR-02: Staff can access all patient records
    BR-03: Only phc_staff can access
    
    Args:
        search_query (str): Patient ID, username, or name
        request_user: Django User object
    
    Returns:
        list: Matching patient records
    
    Raises:
        PHCStaffPermissionError: If not phc_staff role
    """
    role = resolve_phc_role(request_user)
    if role != ROLE_PHC_STAFF and not request_user.is_superuser:
        raise PHCStaffPermissionError('Only PHC staff can search patients')
    
    if not search_query or len(search_query.strip()) < 2:
        return []
    
    query_lower = search_query.strip().lower()
    
    # Search by username, first_name, last_name, or id
    matching_users = User.objects.filter(
        Q(username__icontains=query_lower) |
        Q(first_name__icontains=query_lower) |
        Q(last_name__icontains=query_lower) |
        Q(id__icontains=query_lower)
    ).values('id', 'username', 'first_name', 'last_name')[:20]
    
    results = []
    for user_data in matching_users:
        try:
            medical_profile = MedicalProfile.objects.filter(
                user_id__user__id=user_data['id']
            ).first()
            results.append({
                'patient_id': user_data['id'],
                'username': user_data['username'],
                'full_name': f"{user_data['first_name']} {user_data['last_name']}",
                'blood_type': medical_profile.blood_type if medical_profile else 'N/A',
                'last_appointment': _get_last_appointment_date(user_data['id']),
            })
        except Exception:
            continue
    
    return results


def getPatientHistoryService(patient_id, request_user):
    """
    Get patient's medical history (appointments, prescriptions, visits)
    BR-02: Staff access all records
    BR-03: Only phc_staff
    
    Args:
        patient_id: User ID of patient
        request_user: Django User object
    
    Returns:
        dict: Patient history with appointments, visits, prescriptions
    """
    role = resolve_phc_role(request_user)
    if role != ROLE_PHC_STAFF and not request_user.is_superuser:
        raise PHCStaffPermissionError('Only PHC staff can access patient history')
    
    patient = User.objects.filter(id=patient_id).first()
    if not patient:
        raise PHCStaffError('Patient not found')
    
    # Get recent appointments (all statuses for history view)
    appointments = Appointment.objects.filter(
        user_id=patient_id
    ).select_related('doctor').order_by('-date')[:10]
    
    # Get visits
    visits = Visit.objects.filter(
        patient_id=patient_id
    ).select_related('doctor', 'created_by').order_by('-created_at')[:10]
    
    # Get medical profile
    medical_profile = MedicalProfile.objects.filter(user_id__user_id=patient_id).first()
    
    return {
        'patient_id': patient_id,
        'patient_name': f"{patient.first_name} {patient.last_name}",
        'username': patient.username,
        'medical_profile': _serialize_medical_profile(medical_profile) if medical_profile else None,
        'recent_appointments': [_serialize_appointment(a) for a in appointments],
        'recent_visits': [_serialize_visit(v) for v in visits],
    }


def getPatientPendingAppointmentsService(patient_id, request_user):
    """
    Get ONLY PENDING/BOOKED appointments for a patient (for creating visit records)
    Used by UC-06 to show available appointments to link with visit
    
    BR-02: Staff access all records
    BR-03: Only phc_staff
    
    Args:
        patient_id: User ID of patient
        request_user: Django User object
    
    Returns:
        list: Pending appointments only (status: booked, rescheduled, not completed ones)
    
    Raises:
        PHCStaffPermissionError: If not phc_staff
    """
    role = resolve_phc_role(request_user)
    if role != ROLE_PHC_STAFF and not request_user.is_superuser:
        raise PHCStaffPermissionError('Only PHC staff can access patient appointments')
    
    patient = User.objects.filter(id=patient_id).first()
    if not patient:
        raise PHCStaffError('Patient not found')
    
    # Only fetch appointments that are pending/booked (NOT completed/cancelled/no_show)
    pending_statuses = ['booked', 'rescheduled']
    appointments = Appointment.objects.filter(
        user_id=patient_id,
        status__in=pending_statuses
    ).select_related('doctor').order_by('-date')
    
    return [_serialize_appointment(a) for a in appointments]


def enhanceVisitRecordService(diagnosis, prescription, appointment_id=None, patient_id=None, doctor_id=None, notes=None, request_user=None):
    """
    Enhanced visit record creation - supports both appointment-linked and walk-in visits
    UC-06: Create visit record with diagnosis & prescription
    BR-09: Log action
    
    Args:
        diagnosis: Medical diagnosis text (required)
        prescription: Prescription text (required)
        appointment_id: ID of existing appointment (optional - for appointment-linked visits)
        patient_id: Patient user ID (required if no appointment_id - for walk-in visits)
        doctor_id: Doctor ID (optional for walk-in visits)
        notes: Optional additional notes
        request_user: Django User (staff who created)
    
    Returns:
        dict: Created visit record
    
    Raises:
        PHCStaffError: Validation errors
        PHCStaffPermissionError: If not phc_staff
    """
    role = resolve_phc_role(request_user)
    if role != ROLE_PHC_STAFF and not request_user.is_superuser:
        raise PHCStaffPermissionError('Only PHC staff can create visits')
    
    if not diagnosis or not prescription:
        raise PHCStaffError('Diagnosis and prescription are required')
    
    # Case 1: Appointment-linked visit
    if appointment_id:
        try:
            appointment = Appointment.objects.select_related('user', 'doctor').get(id=int(appointment_id))
        except (Appointment.DoesNotExist, TypeError, ValueError):
            raise PHCStaffError(f'Appointment {appointment_id} not found')
        
        # Check if visit already exists
        if hasattr(appointment, 'visit') and appointment.visit:
            raise PHCStaffError('Visit record already exists for this appointment')
        
        # Create visit linked to appointment
        with transaction.atomic():
            visit = Visit.objects.create(
                appointment=appointment,
                patient=appointment.user,
                doctor=appointment.doctor,
                diagnosis=diagnosis,
                prescription=prescription,
                created_by=request_user,
            )
            
            # Update appointment status to completed
            appointment.status = 'completed'
            appointment.save(update_fields=['status'])
            
            # Log action (BR-09)
            PHCAppointmentAuditLog.objects.create(
                action='visit_created_from_appointment',
                performed_by=request_user,
                appointment=appointment,
                visit=visit,
                metadata=json.dumps({
                    'diagnosis_length': len(diagnosis),
                    'prescription_length': len(prescription),
                    'notes_provided': bool(notes),
                    'visit_type': 'appointment_linked',
                })
            )
        
        return {
            'visit_id': visit.id,
            'appointment_id': appointment.id,
            'patient_id': appointment.user.id,
            'patient_name': appointment.user.get_full_name(),
            'doctor_id': appointment.doctor.id,
            'doctor_name': appointment.doctor.doctor_name,
            'diagnosis': diagnosis,
            'prescription': prescription,
            'visit_type': 'appointment_linked',
            'created_at': visit.created_at.isoformat(),
            'created_by': request_user.username,
        }
    
    # Case 2: Walk-in visit (no appointment)
    elif patient_id:
        try:
            patient = User.objects.get(id=int(patient_id))
        except (User.DoesNotExist, TypeError, ValueError):
            raise PHCStaffError(f'Patient {patient_id} not found')
        
        doctor = None
        if doctor_id:
            try:
                doctor = Doctor.objects.get(id=int(doctor_id))
            except (Doctor.DoesNotExist, TypeError, ValueError):
                pass  # Doctor is optional for walk-in
        
        # Create walk-in visit (not linked to any appointment)
        with transaction.atomic():
            visit = Visit.objects.create(
                appointment=None,  # No appointment for walk-in
                patient=patient,
                doctor=doctor,  # Optional
                diagnosis=diagnosis,
                prescription=prescription,
                created_by=request_user,
            )
            
            # Log action (BR-09)
            PHCAppointmentAuditLog.objects.create(
                action='visit_created_walkin',
                performed_by=request_user,
                visit=visit,
                metadata=json.dumps({
                    'patient_id': patient_id,
                    'doctor_id': doctor_id,
                    'diagnosis_length': len(diagnosis),
                    'prescription_length': len(prescription),
                    'notes_provided': bool(notes),
                    'visit_type': 'walk_in',
                })
            )
        
        return {
            'visit_id': visit.id,
            'appointment_id': None,
            'patient_id': patient.id,
            'patient_name': patient.get_full_name(),
            'doctor_id': doctor.id if doctor else None,
            'doctor_name': doctor.doctor_name if doctor else 'Not assigned',
            'diagnosis': diagnosis,
            'prescription': prescription,
            'visit_type': 'walk_in',
            'created_at': visit.created_at.isoformat(),
            'created_by': request_user.username,
        }
    
    else:
        raise PHCStaffError('Either appointment_id or patient_id is required')


def getVisitDetailService(visit_id, request_user):
    """Get detailed visit record by visit ID"""
    role = resolve_phc_role(request_user)
    if role != ROLE_PHC_STAFF and not request_user.is_superuser:
        raise PHCStaffPermissionError('Only PHC staff can view visit details')

    if not visit_id:
        raise PHCStaffError('visit_id is required')

    try:
        from applications.health_center.models import Visit
        visit = Visit.objects.select_related('appointment', 'doctor', 'patient').get(id=int(visit_id))
    except (Visit.DoesNotExist, TypeError, ValueError):
        raise PHCStaffError('Invalid visit_id')

    return {
        'visit_id': visit.id,
        'appointment_id': visit.appointment.id,
        'patient_id': visit.patient.id,
        'patient_name': visit.patient.user.get_full_name() if hasattr(visit.patient, 'user') else visit.patient.username,
        'doctor_id': visit.doctor.id,
        'doctor_name': visit.doctor.doctor_name,
        'diagnosis': visit.diagnosis,
        'prescription': visit.prescription,
        'created_at': visit.created_at.isoformat(),
        'created_by': visit.created_by.username if visit.created_by else 'N/A',
    }


def updateAppointmentStatusService(appointment_id, new_status, notes, request_user):
    """Update appointment status for PHC staff dashboard actions."""
    role = resolve_phc_role(request_user)
    if role != ROLE_PHC_STAFF and not request_user.is_superuser:
        raise PHCStaffPermissionError('Only PHC staff can update appointment status')

    if not appointment_id:
        raise PHCStaffError('appointment_id is required')

    normalized_status = str(new_status or '').strip().lower()
    allowed_statuses = ['booked', 'completed', 'cancelled', 'no_show', 'rescheduled']
    if normalized_status not in allowed_statuses:
        raise PHCStaffError('Invalid status. Must be one of: booked, completed, cancelled, no_show, rescheduled')

    try:
        appointment = Appointment.objects.select_related('user', 'doctor').get(id=int(appointment_id))
    except (Appointment.DoesNotExist, TypeError, ValueError):
        raise PHCStaffError(f'Appointment {appointment_id} not found')

    with transaction.atomic():
        appointment.status = normalized_status
        appointment.save(update_fields=['status'])

        PHCAppointmentAuditLog.objects.create(
            action='appointment_status_updated',
            performed_by=request_user,
            appointment=appointment,
            metadata=json.dumps({
                'appointment_id': appointment.id,
                'status': normalized_status,
                'notes': notes or '',
            })
        )

    return {
        'appointment_id': appointment.id,
        'patient_name': appointment.user.username,
        'doctor_name': appointment.doctor.doctor_name,
        'appointment_date': appointment.date.isoformat(),
        'time_slot': appointment.time_slot.strftime('%H:%M'),
        'status': appointment.status,
        'notes': notes or '',
        'updated_by': request_user.username,
    }


# ===========================
# UC-07: DOCTOR SCHEDULE
# ===========================

def createDoctorService(doctor_name, doctor_phone, specialization, request_user, active=True):
    """
    Create a new doctor record for PHC operations.
    """
    role = resolve_phc_role(request_user)
    if role != ROLE_PHC_STAFF and not request_user.is_superuser:
        raise PHCStaffPermissionError('Only PHC staff can add doctors')

    doctor_name = (doctor_name or '').strip()
    doctor_phone = (doctor_phone or '').strip()
    specialization = (specialization or '').strip()

    if not doctor_name:
        raise PHCStaffError('Doctor name is required')
    if not doctor_phone:
        raise PHCStaffError('Doctor phone is required')
    if not specialization:
        raise PHCStaffError('Specialization is required')

    duplicate_qs = Doctor.objects.filter(
        doctor_name__iexact=doctor_name,
        doctor_phone=doctor_phone,
    )
    if duplicate_qs.exists():
        raise PHCStaffError('Doctor with same name and phone already exists')

    with transaction.atomic():
        doctor = Doctor.objects.create(
            doctor_name=doctor_name,
            doctor_phone=doctor_phone,
            specialization=specialization,
            active=bool(active),
        )

        PHCAppointmentAuditLog.objects.create(
            action='doctor_created',
            performed_by=request_user,
            metadata=json.dumps({'doctor_id': doctor.id, 'doctor_name': doctor_name})
        )

    return {
        'doctor_id': doctor.id,
        'doctor_name': doctor.doctor_name,
        'doctor_phone': doctor.doctor_phone,
        'specialization': doctor.specialization,
        'active': doctor.active,
    }

def toggleDoctorStatusService(doctor_id, request_user):
    """
    Toggle doctor's active/inactive status
    BR-03: Only phc_staff can toggle status
    BR-09: Log action
    
    Args:
        doctor_id: Doctor ID to toggle
        request_user: Staff user
    
    Returns:
        dict: Updated doctor info with new status
    
    Raises:
        PHCStaffError: If doctor not found
        PHCStaffPermissionError: If not phc_staff
    """
    role = resolve_phc_role(request_user)
    if role != ROLE_PHC_STAFF and not request_user.is_superuser:
        raise PHCStaffPermissionError('Only PHC staff can toggle doctor status')
    
    try:
        doctor = Doctor.objects.get(id=int(doctor_id))
    except (Doctor.DoesNotExist, TypeError, ValueError):
        raise PHCStaffError(f'Doctor {doctor_id} not found')
    
    with transaction.atomic():
        # Toggle status
        old_status = doctor.active
        doctor.active = not doctor.active
        doctor.save(update_fields=['active'])
        
        # Log action (BR-09)
        PHCAppointmentAuditLog.objects.create(
            action='doctor_status_toggled',
            performed_by=request_user,
            metadata=json.dumps({
                'doctor_id': doctor.id,
                'doctor_name': doctor.doctor_name,
                'old_status': old_status,
                'new_status': doctor.active,
            })
        )
    
    return {
        'doctor_id': doctor.id,
        'doctor_name': doctor.doctor_name,
        'specialization': doctor.specialization,
        'phone': doctor.doctor_phone,
        'active': doctor.active,
        'status_changed': True,
    }

def updateDoctorScheduleService(doctor_id, schedule_data, request_user):
    """
    Update or create doctor's weekly schedule
    
    Args:
        doctor_id: Doctor ID
        schedule_data: List of {'day', 'from_time', 'to_time', 'room'}
        request_user: Staff user
    
    Returns:
        dict: Updated schedule info
    """
    role = resolve_phc_role(request_user)
    if role != ROLE_PHC_STAFF and not request_user.is_superuser:
        raise PHCStaffPermissionError('Only PHC staff can manage schedules')
    
    try:
        doctor = Doctor.objects.get(id=doctor_id)
    except Doctor.DoesNotExist:
        raise PHCStaffError(f'Doctor {doctor_id} not found')
    
    with transaction.atomic():
        # Delete existing schedules for this doctor (for week refresh)
        Doctors_Schedule.objects.filter(doctor_id=doctor_id).delete()
        
        # Create new schedules
        created_schedules = []
        for entry in schedule_data:
            schedule = Doctors_Schedule.objects.create(
                doctor_id=doctor,
                day=entry.get('day'),  # 0-6: Mon-Sun
                from_time=entry.get('from_time'),
                to_time=entry.get('to_time'),
                room=entry.get('room', 0),
            )
            created_schedules.append({
                'id': schedule.id,
                'day': schedule.day,
                'from_time': str(schedule.from_time),
                'to_time': str(schedule.to_time),
                'room': schedule.room,
            })
        
        # Audit log
        PHCAppointmentAuditLog.objects.create(
            action='doctor_schedule_updated',
            performed_by=request_user,
            metadata=json.dumps({'doctor_id': doctor_id, 'entries_count': len(created_schedules)})
        )
    
    return {
        'doctor_id': doctor_id,
        'doctor_name': doctor.doctor_name,
        'schedules': created_schedules,
        'updated_at': datetime.datetime.now().isoformat(),
    }


# ===========================
# UC-08: DOCTOR ATTENDANCE
# ===========================

def markDoctorAttendanceService(doctor_id, status, request_user):
    """
    Mark doctor as available/departed
    BR-01: Real-time availability update
    
    Args:
        doctor_id: Doctor ID
        status: 'available', 'departed', 'on_leave'
        request_user: Staff user
    
    Returns:
        dict: Attendance record
    """
    role = resolve_phc_role(request_user)
    if role != ROLE_PHC_STAFF and not request_user.is_superuser:
        raise PHCStaffPermissionError('Only PHC staff can mark attendance')
    
    if status not in ['available', 'departed', 'on_leave']:
        raise PHCStaffError('Invalid status. Must be: available, departed, on_leave')
    
    try:
        doctor = Doctor.objects.get(id=doctor_id)
    except Doctor.DoesNotExist:
        raise PHCStaffError(f'Doctor {doctor_id} not found')
    
    with transaction.atomic():
        attendance = DoctorAttendance.objects.create(
            doctor=doctor,
            status=status,
            marked_by=request_user,
        )
        
        # If marked as departed, invalidate appointments scheduled after this time
        if status == 'departed':
            _handle_doctor_departure(doctor, request_user)
        
        # Audit log
        PHCAppointmentAuditLog.objects.create(
            action='doctor_attendance_marked',
            performed_by=request_user,
            metadata=json.dumps({'doctor_id': doctor_id, 'status': status})
        )
    
    return {
        'doctor_id': doctor_id,
        'doctor_name': doctor.doctor_name,
        'status': attendance.status,
        'timestamp': attendance.timestamp.isoformat(),
        'marked_by': request_user.username,
    }


# ===========================
# UC-09: INVENTORY
# ===========================

def manageInventoryService(medicine_id, quantity_change, reason, request_user):
    """
    Add or deduct medicine stock
    BR-07: Check threshold, trigger alert
    BR-09: Log transaction
    
    Args:
        medicine_id: Medicine ID
        quantity_change: Positive (add) or negative (deduct)
        reason: Reason for change
        request_user: Staff user
    
    Returns:
        dict: Updated inventory info + alert if triggered
    """
    role = resolve_phc_role(request_user)
    if role != ROLE_PHC_STAFF and not request_user.is_superuser:
        raise PHCStaffPermissionError('Only PHC staff can manage inventory')
    
    try:
        medicine = All_Medicine.objects.get(id=medicine_id)
    except All_Medicine.DoesNotExist:
        raise PHCStaffError(f'Medicine {medicine_id} not found')
    
    with transaction.atomic():
        # Get or create inventory
        inventory, created = Inventory.objects.get_or_create(
            medicine=medicine,
            defaults={'stock_quantity': 0}
        )
        
        # Update stock
        inventory.stock_quantity += quantity_change
        if inventory.stock_quantity < 0:
            raise PHCStaffError('Not enough stock to deduct')
        
        inventory.last_updated_by = request_user
        inventory.save()
        
        # Log transaction (BR-09)
        transaction_obj = InventoryTransaction.objects.create(
            inventory=inventory,
            transaction_type='add' if quantity_change > 0 else 'deduct',
            quantity_change=quantity_change,
            reason=reason,
            performed_by=request_user,
        )
        
        # Check threshold (BR-07)
        alert = None
        if inventory.is_low_stock():
            alert = LowStockAlert.objects.create(
                inventory=inventory,
                current_stock=inventory.stock_quantity,
                threshold=inventory.reorder_threshold,
            )
        else:
            # Auto-resolve any active alerts once stock recovers above threshold.
            LowStockAlert.objects.filter(
                inventory=inventory,
                acknowledged=False,
            ).update(
                acknowledged=True,
                acknowledged_by=request_user,
            )
    
    return {
        'medicine_id': medicine_id,
        'medicine_name': medicine.medicine_name,
        'stock_quantity': inventory.stock_quantity,
        'reorder_threshold': inventory.reorder_threshold,
        'is_low_stock': inventory.is_low_stock(),
        'alert_triggered': alert is not None,
        'alert_id': alert.id if alert else None,
        'transaction_id': transaction_obj.id,
        'updated_at': inventory.last_updated.isoformat(),
    }


def getInventoryService(request_user, low_stock_only=False):
    """
    Get inventory overview
    
    Args:
        request_user: Staff user
        low_stock_only: Filter to only low stock items
    
    Returns:
        list: Inventory items
    """
    role = resolve_phc_role(request_user)
    if role != ROLE_PHC_STAFF and not request_user.is_superuser:
        raise PHCStaffPermissionError('Only PHC staff can view inventory')
    
    qs = Inventory.objects.select_related('medicine').order_by('medicine__medicine_name')
    
    if low_stock_only:
        qs = qs.filter(stock_quantity__lte=Inventory.objects.values('reorder_threshold'))
    
    return [
        {
            'inventory_id': inv.id,
            'medicine_id': inv.medicine.id,
            'medicine_name': inv.medicine.medicine_name,
            'stock_quantity': inv.stock_quantity,
            'reorder_threshold': inv.reorder_threshold,
            'is_low_stock': inv.is_low_stock(),
            'last_updated': inv.last_updated.isoformat(),
        }
        for inv in qs
    ]


def createMedicineService(
    medicine_name,
    brand_name,
    manufacturer_name,
    constituents,
    pack_size_label,
    initial_stock,
    reorder_threshold,
    request_user,
):
    """
    Create a medicine record and initialize inventory.
    """
    role = resolve_phc_role(request_user)
    if role != ROLE_PHC_STAFF and not request_user.is_superuser:
        raise PHCStaffPermissionError('Only PHC staff can add medicines')

    if not medicine_name:
        raise PHCStaffError('Medicine name is required')

    initial_stock = int(initial_stock or 0)
    reorder_threshold = int(reorder_threshold or 10)

    if initial_stock < 0:
        raise PHCStaffError('Initial stock cannot be negative')
    if reorder_threshold < 0:
        raise PHCStaffError('Reorder threshold cannot be negative')

    duplicate_qs = All_Medicine.objects.filter(
        medicine_name__iexact=medicine_name.strip(),
        brand_name__iexact=(brand_name or '').strip() or 'NOT_SET',
    )
    if duplicate_qs.exists():
        raise PHCStaffError('Medicine with same name and brand already exists')

    with transaction.atomic():
        medicine = All_Medicine.objects.create(
            medicine_name=medicine_name.strip(),
            brand_name=(brand_name or 'NOT_SET').strip() or 'NOT_SET',
            constituents=(constituents or 'NOT_SET').strip() or 'NOT_SET',
            manufacturer_name=(manufacturer_name or 'NOT_SET').strip() or 'NOT_SET',
            threshold=reorder_threshold,
            pack_size_label=(pack_size_label or 'NOT_SET').strip() or 'NOT_SET',
        )

        inventory = Inventory.objects.create(
            medicine=medicine,
            stock_quantity=initial_stock,
            reorder_threshold=reorder_threshold,
            last_updated_by=request_user,
        )

        PHCAppointmentAuditLog.objects.create(
            action='medicine_created',
            performed_by=request_user,
            metadata=json.dumps({'medicine_id': medicine.id, 'initial_stock': initial_stock})
        )

    return {
        'medicine_id': medicine.id,
        'medicine_name': medicine.medicine_name,
        'brand_name': medicine.brand_name,
        'stock_quantity': inventory.stock_quantity,
        'reorder_threshold': inventory.reorder_threshold,
        'is_low_stock': inventory.is_low_stock(),
    }


def getAvailableMedicinesService(request_user):
    """
    Get all medicines that are currently in stock (for staff to prescribe)
    BR-02: Staff access inventory
    BR-03: Only phc_staff
    
    Args:
        request_user: Django User object
    
    Returns:
        list: Available medicines with current stock
    
    Raises:
        PHCStaffPermissionError: If not phc_staff
    """
    role = resolve_phc_role(request_user)
    if role != ROLE_PHC_STAFF and not request_user.is_superuser:
        raise PHCStaffPermissionError('Only PHC staff can view medicines')
    
    # Get all medicines with current inventory > 0
    medicines = All_Medicine.objects.all()
    available = []
    
    for medicine in medicines:
        try:
            inventory = Inventory.objects.get(medicine=medicine)
            if inventory.stock_quantity > 0:
                available.append({
                    'id': medicine.id,
                    'medicine_name': medicine.medicine_name,
                    'brand_name': medicine.brand_name,
                    'quantity': inventory.stock_quantity,
                    'reorder_threshold': inventory.reorder_threshold,
                })
        except Inventory.DoesNotExist:
            pass  # No inventory entry, skip
    
    return available


def useMedicinesFromPrescriptionService(visit_id, medicines, request_user):
    """
    Use/reduce medicines from inventory when prescription is written
    BR-02: Staff action
    BR-03: Only phc_staff
    BR-09: Log action
    
    Args:
        visit_id: ID of visit record
        medicines: List of {'medicine_id', 'quantity_used'}
        request_user: Django User object
    
    Returns:
        dict: Result with deducted medicines
    
    Raises:
        PHCStaffPermissionError: If not phc_staff
        PHCStaffError: If medicine not found or insufficient stock
    """
    role = resolve_phc_role(request_user)
    if role != ROLE_PHC_STAFF and not request_user.is_superuser:
        raise PHCStaffPermissionError('Only PHC staff can use medicines')
    
    if not medicines or len(medicines) == 0:
        raise PHCStaffError('No medicines to deduct')
    
    try:
        visit = Visit.objects.get(id=int(visit_id))
    except (Visit.DoesNotExist, TypeError, ValueError):
        raise PHCStaffError(f'Visit {visit_id} not found')
    
    deducted = []
    
    with transaction.atomic():
        for med in medicines:
            if not isinstance(med, dict):
                raise PHCStaffError('Invalid medicine entry format')

            # Keep API contract tolerant: ignore unknown keys and process only required fields.
            normalized_med = {
                'medicine_id': med.get('medicine_id'),
                'quantity': med.get('quantity', med.get('quantity_used', 1)),
            }
            medicine_id = normalized_med.get('medicine_id')
            raw_quantity = normalized_med.get('quantity')

            if medicine_id is None or raw_quantity is None:
                raise PHCStaffError('Invalid medicine data: medicine_id and quantity are required')

            try:
                medicine_id = int(medicine_id)
            except (TypeError, ValueError):
                raise PHCStaffError(f'Invalid medicine_id: {medicine_id}')

            try:
                quantity_used = int(raw_quantity)
            except (TypeError, ValueError):
                raise PHCStaffError(f'Invalid quantity: {raw_quantity}')
            
            if quantity_used <= 0:
                raise PHCStaffError(f'Invalid quantity: {quantity_used}')
            
            try:
                medicine = All_Medicine.objects.get(id=medicine_id)
            except (All_Medicine.DoesNotExist, TypeError, ValueError):
                raise PHCStaffError(f'Medicine {medicine_id} not found')
            
            try:
                inventory = Inventory.objects.get(medicine=medicine)
            except Inventory.DoesNotExist:
                raise PHCStaffError(f'No inventory entry for {medicine.medicine_name}')
            
            if inventory.stock_quantity < quantity_used:
                raise PHCStaffError(
                    f'Insufficient stock for {medicine.medicine_name}. '
                    f'Available: {inventory.stock_quantity}, Needed: {quantity_used}'
                )
            
            # Deduct from inventory
            inventory.stock_quantity -= quantity_used
            inventory.last_updated_by = request_user
            inventory.save()
            
            # Log transaction
            InventoryTransaction.objects.create(
                inventory=inventory,
                transaction_type='deduct',
                quantity_change=-quantity_used,
                reason=f'Used in visit {visit_id}',
                performed_by=request_user,
            )
            
            # Log audit
            PHCAppointmentAuditLog.objects.create(
                action='medicine_used_in_visit',
                performed_by=request_user,
                visit=visit,
                metadata=json.dumps({
                    'medicine_id': medicine.id,
                    'medicine_name': medicine.medicine_name,
                    'quantity_used': quantity_used,
                    'remaining_stock': inventory.stock_quantity,
                })
            )
            
            deducted.append({
                'medicine_id': medicine.id,
                'medicine_name': medicine.medicine_name,
                'quantity_used': quantity_used,
                'remaining_stock': inventory.stock_quantity,
            })
    
    return {
        'visit_id': visit_id,
        'medicines_deducted': deducted,
        'deducted_count': len(deducted),
    }


# ===========================
# UC-10/UC-14: REQUISITION
# ===========================

def _parse_required_supplies_from_reason(reason_text):
    """Extract required supplies from reason suffix: '| Required: item xN, ...'."""
    marker = '| Required:'
    parsed = []
    if not reason_text or marker not in reason_text:
        return parsed

    supplies_text = reason_text.split(marker, 1)[1].strip()
    if not supplies_text:
        return parsed

    for token in supplies_text.split(','):
        entry = str(token).strip()
        if not entry:
            continue

        quantity = 1
        item_name = entry
        if ' x' in entry:
            item_name, qty_raw = entry.rsplit(' x', 1)
            try:
                quantity = int(str(qty_raw).strip())
            except (TypeError, ValueError):
                quantity = 1

        item_name = str(item_name).strip()
        if item_name and quantity > 0:
            parsed.append({'item': item_name, 'quantity': quantity})

    return parsed


def _get_or_create_medicine_for_supply(supply_name):
    """Map a non-medicine supply label to All_Medicine so inventory can track it."""
    normalized_name = str(supply_name).strip()
    if not normalized_name:
        raise PHCStaffError('supply item name cannot be empty')

    medicine = All_Medicine.objects.filter(medicine_name__iexact=normalized_name).first()
    if medicine:
        return medicine

    return All_Medicine.objects.create(
        medicine_name=normalized_name,
        brand_name=normalized_name,
        constituents='NOT_SET',
        manufacturer_name='NOT_SET',
        threshold=10,
        pack_size_label='SUPPLY',
    )

def createRequisitionService(items_data, reason, request_user, requested_supplies=None, notes=''):
    """
    Create medicine requisition request
    
    Args:
        items_data: List of {'medicine_id', 'quantity', 'priority'}
        reason: Reason for requisition
        request_user: Staff user
    
    Returns:
        dict: Created requisition
    """
    role = resolve_phc_role(request_user)
    if role != ROLE_PHC_STAFF and not request_user.is_superuser:
        raise PHCStaffPermissionError('Only PHC staff can create requisitions')

    if not reason or not str(reason).strip():
        raise PHCStaffError('reason is required')

    if requested_supplies is None:
        requested_supplies = []

    if not isinstance(items_data, list):
        raise PHCStaffError('items must be a list')

    if not isinstance(requested_supplies, list):
        raise PHCStaffError('requested_supplies must be a list')

    if len(items_data) == 0 and len(requested_supplies) == 0:
        raise PHCStaffError('Select at least one required supply or medicine item')

    reason_value = str(reason).strip()
    normalized_supplies = []
    if requested_supplies:
        for entry in requested_supplies:
            if isinstance(entry, dict):
                item_name = str(entry.get('item', '')).strip()
                qty = entry.get('quantity', 1)
            else:
                item_name = str(entry).strip()
                qty = 1

            try:
                qty = int(qty)
            except (TypeError, ValueError):
                raise PHCStaffError('requested_supplies quantity must be a valid integer')

            if not item_name:
                continue
            if qty <= 0:
                raise PHCStaffError('requested_supplies quantity must be greater than 0')

            normalized_supplies.append({'item': item_name, 'quantity': qty})

    if normalized_supplies:
        supplies_text = ', '.join([f"{s['item']} x{s['quantity']}" for s in normalized_supplies])
        reason_value = f"{reason_value} | Required: {supplies_text}"
    
    with transaction.atomic():
        requisition = Requisition.objects.create(
            created_by=request_user,
            reason=reason_value,
            status='submitted',
        )
        
        items_list = []
        for item_data in items_data:
            if not isinstance(item_data, dict):
                raise PHCStaffError('Each item must be an object with medicine_id and quantity')

            medicine_id = item_data.get('medicine_id')
            if medicine_id is None:
                raise PHCStaffError('medicine_id is required for each item')

            try:
                medicine_id = int(medicine_id)
            except (TypeError, ValueError):
                raise PHCStaffError('medicine_id must be a valid integer')

            quantity_requested = item_data.get('quantity', 0)
            try:
                quantity_requested = int(quantity_requested)
            except (TypeError, ValueError):
                raise PHCStaffError('quantity must be a valid integer')

            if quantity_requested <= 0:
                raise PHCStaffError('quantity must be greater than 0')

            try:
                medicine = All_Medicine.objects.get(id=medicine_id)
            except All_Medicine.DoesNotExist:
                raise PHCStaffError(f"Medicine {medicine_id} not found")
            
            req_item = RequisitionItem.objects.create(
                requisition=requisition,
                medicine=medicine,
                quantity_requested=quantity_requested,
                priority=item_data.get('priority', 'normal'),
            )
            items_list.append({
                'id': req_item.id,
                'medicine_id': medicine.id,
                'medicine_name': medicine.medicine_name,
                'quantity_requested': req_item.quantity_requested,
                'priority': req_item.priority,
            })

        # Persist required supplies as requisition items too, so fulfillment can update inventory.
        for supply in normalized_supplies:
            medicine = _get_or_create_medicine_for_supply(supply['item'])
            req_item = RequisitionItem.objects.create(
                requisition=requisition,
                medicine=medicine,
                quantity_requested=supply['quantity'],
                priority='normal',
            )
            items_list.append({
                'id': req_item.id,
                'medicine_id': medicine.id,
                'medicine_name': medicine.medicine_name,
                'quantity_requested': req_item.quantity_requested,
                'priority': req_item.priority,
            })
        
        # Audit log
        PHCAppointmentAuditLog.objects.create(
            action='requisition_created',
            performed_by=request_user,
            metadata=json.dumps({
                'requisition_id': requisition.id,
                'items_count': len(items_list),
                'requested_supplies': normalized_supplies,
                'notes': notes,
            })
        )

        _push_phc_notification_event(
            event_type='requisition_created',
            title='Requisition Created',
            message=f'Requisition #{requisition.id} has been created',
            request_user=request_user,
            metadata={
                'requisition_id': requisition.id,
                'status': requisition.status,
            },
        )
    
    return {
        'requisition_id': requisition.id,
        'status': requisition.status,
        'reason': reason_value,
        'requested_supplies': normalized_supplies,
        'notes': notes,
        'items': items_list,
        'created_by': request_user.username,
        'created_at': requisition.created_at.isoformat(),
    }


def getRequisitionsForStaffService(request_user):
    """
    Get all requisitions for staff dashboard.

    Returns response fields aligned with RequisitionManagement UI.
    """
    role = resolve_phc_role(request_user)
    if role != ROLE_PHC_STAFF and not request_user.is_superuser:
        raise PHCStaffPermissionError('Only PHC staff can view requisitions')

    requisitions = Requisition.objects.prefetch_related('items_list', 'items_list__medicine').order_by('-created_at')

    status_map = {
        'submitted': 'pending',
        'approved': 'approved',
        'fulfilled': 'fulfilled',
        'rejected': 'rejected',
        'closed': 'fulfilled',
    }

    priority_map = {
        'urgent': 'high',
        'normal': 'normal',
    }

    result = []
    for req in requisitions:
        item_rows = list(req.items_list.all())

        requested_supplies_qty_total = 0
        # Backward compatibility for older requisitions where supplies were only encoded in reason text.
        if not item_rows:
            for supply in _parse_required_supplies_from_reason(req.reason):
                requested_supplies_qty_total += max(int(supply['quantity']), 0)

        medicine_qty_total = sum(max(int(item.quantity_requested or 0), 0) for item in item_rows)
        total_requested_count = medicine_qty_total + requested_supplies_qty_total

        if any(item.priority == 'urgent' for item in item_rows):
            priority = 'high'
        elif item_rows:
            priority = priority_map.get(item_rows[0].priority, 'normal')
        else:
            priority = 'normal'

        # Build items list with details for fulfill modal
        items_list = [
            {
                'requisition_item_id': item.id,
                'medicine_name': item.medicine.medicine_name if hasattr(item, 'medicine') else 'Unknown',
                'quantity_requested': item.quantity_requested,
                'quantity_fulfilled': item.quantity_fulfilled,
                'priority': item.priority,
            }
            for item in item_rows
        ]

        result.append({
            'requisition_id': req.id,
            'reason': req.reason,
            'created_date': req.created_at.strftime('%Y-%m-%d'),
            'status': status_map.get(req.status, req.status),
            'priority': priority,
            'items_count': total_requested_count,
            'items_list': items_list,
        })

    return result


def approveRequisitionService(requisition_id, action, request_user, notes=''):
    """
    UC-16: Approve or reject a requisition.

    Args:
        requisition_id: Requisition ID
        action: 'approve' or 'reject'
        request_user: PHC staff user
        notes: Optional decision notes

    Returns:
        dict: Updated requisition state
    """
    role = resolve_phc_role(request_user)
    if role != ROLE_PHC_STAFF and not request_user.is_superuser:
        raise PHCStaffPermissionError('Only PHC staff can mark requisition decision')

    try:
        requisition = Requisition.objects.get(id=requisition_id)
    except Requisition.DoesNotExist:
        raise PHCStaffError(f'Requisition {requisition_id} not found')

    normalized_action = str(action or '').strip().lower()
    if normalized_action not in ['approve', 'reject']:
        raise PHCStaffError("action must be 'approve' or 'reject'")

    if requisition.status not in ['submitted', 'approved']:
        raise PHCStaffError('Only submitted or approved requisitions can be updated')

    with transaction.atomic():
        if normalized_action == 'approve':
            requisition.status = 'approved'
            requisition.approved_by = request_user
            audit_action = 'requisition_approved'
        else:
            requisition.status = 'rejected'
            requisition.approved_by = None
            audit_action = 'requisition_rejected'

        requisition.save(update_fields=['status', 'approved_by'])

        PHCAppointmentAuditLog.objects.create(
            action=audit_action,
            performed_by=request_user,
            metadata=json.dumps({
                'requisition_id': requisition.id,
                'action': normalized_action,
                'notes': notes,
            })
        )

        _push_phc_notification_event(
            event_type=f'requisition_{normalized_action}d',
            title=f"Requisition {normalized_action.title()}d",
            message=f"Requisition #{requisition.id} was {normalized_action}d",
            request_user=request_user,
            metadata={
                'requisition_id': requisition.id,
                'status': requisition.status,
                'notes': notes,
            },
        )

    return {
        'requisition_id': requisition.id,
        'status': requisition.status,
        'action': normalized_action,
        'updated_by': request_user.username,
    }


def fulfillRequisitionService(requisition_id, items_fulfillment, request_user):
    """
    Mark requisition as fulfilled and update inventory
    
    Args:
        requisition_id: Requisition ID
        items_fulfillment: List of {'requisition_item_id', 'quantity_fulfilled'}
        request_user: Staff user (compounder)
    
    Returns:
        dict: Updated requisition + inventory changes
    """
    role = resolve_phc_role(request_user)
    if role not in [ROLE_PHC_STAFF, 'authority'] and not request_user.is_superuser:
        raise PHCStaffPermissionError('Only PHC staff can fulfill requisitions')
    
    try:
        requisition = Requisition.objects.get(id=requisition_id)
    except Requisition.DoesNotExist:
        raise PHCStaffError(f'Requisition {requisition_id} not found')
    
    # Allow fulfillment from submitted status (compounder creates and fulfills in one flow)
    if requisition.status not in ['submitted', 'approved']:
        raise PHCStaffError('Requisition must be in submitted or approved status for fulfillment')
    
    with transaction.atomic():
        # If client sends no items, auto-fulfill existing requisition items by requested qty.
        if not isinstance(items_fulfillment, list):
            items_fulfillment = []

        if len(items_fulfillment) == 0:
            existing_items = list(requisition.items_list.all())
            if existing_items:
                items_fulfillment = [
                    {
                        'requisition_item_id': item.id,
                        'quantity_fulfilled': int(item.quantity_requested or 0),
                    }
                    for item in existing_items
                ]
            else:
                # Backfill legacy supply-only requisitions and fulfill them in one step.
                legacy_supplies = _parse_required_supplies_from_reason(requisition.reason)
                for supply in legacy_supplies:
                    medicine = _get_or_create_medicine_for_supply(supply['item'])
                    req_item = RequisitionItem.objects.create(
                        requisition=requisition,
                        medicine=medicine,
                        quantity_requested=supply['quantity'],
                        priority='normal',
                    )
                    items_fulfillment.append(
                        {
                            'requisition_item_id': req_item.id,
                            'quantity_fulfilled': int(supply['quantity']),
                        }
                    )

        total_fulfilled_qty = 0
        for item_fulfill in items_fulfillment:
            try:
                req_item = RequisitionItem.objects.get(
                    id=item_fulfill['requisition_item_id'],
                    requisition=requisition
                )
            except RequisitionItem.DoesNotExist:
                raise PHCStaffError(f"Item not found in requisition")

            try:
                quantity_fulfilled = int(item_fulfill.get('quantity_fulfilled', 0))
            except (TypeError, ValueError):
                raise PHCStaffError('quantity_fulfilled must be a valid integer')

            if quantity_fulfilled < 0:
                raise PHCStaffError('quantity_fulfilled cannot be negative')

            if quantity_fulfilled > int(req_item.quantity_requested or 0):
                raise PHCStaffError('quantity_fulfilled cannot exceed quantity_requested')

            req_item.quantity_fulfilled = quantity_fulfilled
            req_item.save(update_fields=['quantity_fulfilled'])

            if quantity_fulfilled <= 0:
                continue

            total_fulfilled_qty += quantity_fulfilled
            
            # Auto-update inventory
            inventory, _ = Inventory.objects.get_or_create(
                medicine=req_item.medicine,
                defaults={'stock_quantity': 0}
            )
            inventory.stock_quantity += quantity_fulfilled
            inventory.last_updated_by = request_user
            inventory.save(update_fields=['stock_quantity', 'last_updated_by', 'last_updated'])

            InventoryTransaction.objects.create(
                inventory=inventory,
                transaction_type='add',
                quantity_change=quantity_fulfilled,
                reason=f'Requisition #{requisition.id} fulfilled',
                performed_by=request_user,
            )

        if total_fulfilled_qty <= 0:
            raise PHCStaffError('At least one requisition item must have quantity_fulfilled > 0')
        
        # Mark requisition as fulfilled
        requisition.status = 'fulfilled'
        requisition.fulfilled_by = request_user
        requisition.fulfilled_at = timezone.now()
        requisition.save()
        
        # Audit log
        PHCAppointmentAuditLog.objects.create(
            action='requisition_fulfilled',
            performed_by=request_user,
            metadata=json.dumps({'requisition_id': requisition_id})
        )

        _push_phc_notification_event(
            event_type='requisition_fulfilled',
            title='Requisition Fulfilled',
            message=f'Requisition #{requisition.id} has been marked fulfilled',
            request_user=request_user,
            metadata={
                'requisition_id': requisition.id,
                'status': requisition.status,
            },
        )
    
    return {
        'requisition_id': requisition.id,
        'status': requisition.status,
        'fulfilled_by': request_user.username,
        'fulfilled_at': requisition.fulfilled_at.isoformat(),
    }


# ===========================
# UC-11: AMBULANCE LOG
# ===========================

def logAmbulanceService(patient_name, pickup_location, destination, status, request_user, notes=''):
    """
    Log ambulance usage
    
    Args:
        patient_name: Name of patient
        pickup_location: Where ambulance picks up
        destination: Where patient goes
        status: Current status
        request_user: Staff user
        notes: Optional notes
    
    Returns:
        dict: Ambulance log entry
    """
    role = resolve_phc_role(request_user)
    if role != ROLE_PHC_STAFF and not request_user.is_superuser:
        raise PHCStaffPermissionError('Only PHC staff can log ambulance usage')
    
    ambulance_log = AmbulanceLog.objects.create(
        patient_name=patient_name,
        pickup_location=pickup_location,
        destination=destination,
        status=status,
        log_created_by=request_user,
        notes=notes,
    )
    
    return {
        'ambulance_log_id': ambulance_log.id,
        'patient_name': ambulance_log.patient_name,
        'destination': ambulance_log.destination,
        'status': ambulance_log.status,
        'created_at': ambulance_log.requested_at.isoformat(),
        'logged_by': request_user.username,
    }


# ===========================
# UC-12: ANNOUNCEMENTS
# ===========================

def createAnnouncementService(title, content, request_user, expires_at=None):
    """
    Broadcast announcement to all users
    
    Args:
        title: Announcement title
        content: Message content
        request_user: Staff user
        expires_at: Optional expiration datetime
    
    Returns:
        dict: Announcement record
    """
    role = resolve_phc_role(request_user)
    if role != ROLE_PHC_STAFF and not request_user.is_superuser:
        raise PHCStaffPermissionError('Only PHC staff can create announcements')
    
    announcement = Announcement.objects.create(
        title=title,
        content=content,
        created_by=request_user,
        expires_at=expires_at,
    )
    
    return {
        'announcement_id': announcement.id,
        'title': announcement.title,
        'content': announcement.content,
        'created_by': request_user.username,
        'created_at': announcement.created_at.isoformat(),
        'published': announcement.published,
    }


def getAnnouncementsService(request_user):
    """
    Get active announcements
    """
    now = timezone.now()
    announcements = Announcement.objects.filter(
        published=True,
        expires_at__isnull=True
    ) | Announcement.objects.filter(
        published=True,
        expires_at__gt=now
    )
    
    return [
        {
            'announcement_id': a.id,
            'title': a.title,
            'content': a.content,
            'created_by': a.created_by.first_name or a.created_by.username,
            'created_at': a.created_at.isoformat(),
        }
        for a in announcements.order_by('-created_at')
    ]


# ===========================
# UC-15: REIMBURSEMENT PROCESSING
# ===========================

AUDITOR_STATUS_VERIFICATION_PENDING = 'pending_accounts_verification'
AUDITOR_STATUS_AUTHORITY_PENDING = 'authority_approval_pending'


def _ensure_auditor_access(request_user):
    """Allow both auditor and compounder (PHC staff) to access reimbursement workflow."""
    user_type = str(getattr(getattr(request_user, 'extrainfo', None), 'user_type', '')).strip().lower()
    if user_type != 'staff' and user_type != 'compounder' and not request_user.is_superuser:
        raise PHCStaffPermissionError('Only staff users can access reimbursement workflow')

    derived_roles = set()
    
    # Check if user is specifically a compounder
    if user_type == 'compounder':
        derived_roles.add('compounder')
    
    # Check role sources for roles
    for candidate in [
        getattr(getattr(request_user, 'phc_role_profile', None), 'role', None),
        getattr(getattr(request_user, 'phc_staff_profile', None), 'role_type', None),
    ]:
        if candidate:
            normalized = str(candidate).strip().lower()
            if normalized == 'accounts' or 'audit' in normalized:
                derived_roles.add('auditor')

    try:
        from applications.globals.models import HoldsDesignation

        designation_names = HoldsDesignation.objects.filter(working=request_user).values_list('designation__name', flat=True)
        for name in designation_names:
            normalized = str(name or '').strip().lower()
            if 'auditor' in normalized or 'audit' in normalized or 'accounts' in normalized:
                derived_roles.add('auditor')
            elif 'compounder' in normalized or 'phc staff' in normalized:
                derived_roles.add('compounder')
    except Exception:
        pass

    if 'auditor' not in derived_roles and 'compounder' not in derived_roles and not request_user.is_superuser:
        raise PHCStaffPermissionError('Only auditor or compounder role can process reimbursement claims')


def _get_claim_or_raise(claim_id):
    if not claim_id:
        raise PHCStaffError('claim_id is required')

    try:
        return PHCReimbursementClaim.objects.select_related('user').get(id=int(claim_id))
    except (PHCReimbursementClaim.DoesNotExist, TypeError, ValueError):
        raise PHCStaffError(f'Claim {claim_id} not found')


def _audit_reimbursement_action(claim, request_user, action, metadata):
    PHCReimbursementAuditLog.objects.create(
        action=action,
        performed_by=request_user,
        claim=claim,
        metadata=json.dumps(metadata or {}),
    )


def _serialize_claim_for_auditor(claim, request=None):
    documents = []
    try:
        for doc in claim.documents.all():
            try:
                file_url = doc.file.url if doc.file else None
                # Build absolute URL if request is available
                if file_url and request:
                    file_url = request.build_absolute_uri(file_url)
            except (ValueError, AttributeError):
                file_url = None
            
            documents.append({
                'id': doc.id,
                'name': doc.original_name,
                'url': file_url,
                'uploaded_at': doc.uploaded_at.isoformat(),
            })
    except Exception:
        # If documents can't be loaded, continue without them
        documents = []
    
    return {
        'claim_id': claim.id,
        'user_id': claim.user.id,
        'user_name': f"{claim.user.first_name} {claim.user.last_name}".strip() or claim.user.username,
        'amount': float(claim.amount),
        'reason': claim.reason,
        'status': claim.status,
        'created_at': claim.created_at.isoformat(),
        'updated_by': claim.updated_by.username if claim.updated_by else None,
        'documents': documents,
    }


def getPendingReimbursementClaimsForAuditorService(request_user, status_filter=None, request=None):
    _ensure_auditor_access(request_user)

    # Determine if user is compounder or auditor
    is_compounder = False
    user_type = str(getattr(getattr(request_user, 'extrainfo', None), 'user_type', '')).strip().lower()
    
    # Compounder is identified by user_type='compounder'
    if user_type == 'compounder':
        is_compounder = True
    else:
        # Check designations for Compounder role
        try:
            from applications.globals.models import HoldsDesignation
            has_compounder_designation = HoldsDesignation.objects.filter(
                working=request_user,
                designation__name__iexact='Compounder'
            ).exists()
            if has_compounder_designation:
                is_compounder = True
        except Exception:
            pass

    queryset = PHCReimbursementClaim.objects.select_related('user').prefetch_related('processing_logs', 'documents').order_by('-created_at')
    
    # Apply role-based status filter
    if is_compounder:
        # Compounder sees only submitted claims for validity check
        queryset = queryset.filter(status='submitted')
    else:
        # Auditor sees pending verification claims
        queryset = queryset.filter(status=AUDITOR_STATUS_VERIFICATION_PENDING)
    
    # Allow explicit status filter override if provided
    if status_filter:
        queryset = queryset.filter(status=status_filter)

    return [_serialize_claim_for_auditor(claim, request) for claim in queryset]


def verifyClaimService(claim_id, notes, request_user):
    _ensure_auditor_access(request_user)
    claim = _get_claim_or_raise(claim_id)

    # Compounder cannot verify (only auditor can)
    user_type = str(getattr(getattr(request_user, 'extrainfo', None), 'user_type', '')).strip().lower()
    is_compounder = False
    
    if user_type == 'compounder':
        is_compounder = True
    else:
        # Check designations for Compounder role
        try:
            from applications.globals.models import HoldsDesignation
            has_compounder_designation = HoldsDesignation.objects.filter(
                working=request_user,
                designation__name__iexact='Compounder'
            ).exists()
            if has_compounder_designation:
                is_compounder = True
        except Exception:
            pass
    
    if is_compounder:
        raise PHCStaffError('Compounder cannot verify claims. Only auditors can verify claims.')

    if claim.status not in [AUDITOR_STATUS_VERIFICATION_PENDING]:
        raise PHCStaffError('Claim is not in auditor verification stage')

    with transaction.atomic():
        log = ReimbursementProcessingLog.objects.create(
            claim=claim,
            action='verified',
            performed_by=request_user,
            notes=notes or '',
        )
        claim.status = AUDITOR_STATUS_AUTHORITY_PENDING
        claim.updated_by = request_user
        claim.save(update_fields=['status', 'updated_by'])
        _audit_reimbursement_action(
            claim,
            request_user,
            'AUDITOR_CLAIM_VERIFIED',
            {
                'claim_id': claim.id,
                'from_status': AUDITOR_STATUS_VERIFICATION_PENDING,
                'to_status': AUDITOR_STATUS_AUTHORITY_PENDING,
                'notes': notes or '',
            },
        )

    return {
        'claim_id': claim.id,
        'status': claim.status,
        'action': 'verified',
        'verified_by': request_user.username,
        'verified_at': log.timestamp.isoformat(),
    }

def forwardClaimService(claim_id, notes, request_user):
    _ensure_auditor_access(request_user)
    claim = _get_claim_or_raise(claim_id)

    # Determine if user is compounder or auditor
    is_compounder = False
    user_type = str(getattr(getattr(request_user, 'extrainfo', None), 'user_type', '')).strip().lower()
    
    # Compounder is identified by user_type='compounder'
    if user_type == 'compounder':
        is_compounder = True
    else:
        # Check designations for Compounder role
        try:
            from applications.globals.models import HoldsDesignation
            has_compounder_designation = HoldsDesignation.objects.filter(
                working=request_user,
                designation__name__iexact='Compounder'
            ).exists()
            if has_compounder_designation:
                is_compounder = True
        except Exception:
            pass

    # Compounder can forward from 'submitted', auditor from verification stage
    if is_compounder and claim.status not in ['submitted']:
        raise PHCStaffError('Only submitted claims can be forwarded by compounder for auditor review')
    elif not is_compounder and claim.status not in [AUDITOR_STATUS_VERIFICATION_PENDING]:
        raise PHCStaffError('Only claims in auditor verification stage can be forwarded by auditor')

    with transaction.atomic():
        log = ReimbursementProcessingLog.objects.create(
            claim=claim,
            action='forwarded',
            performed_by=request_user,
            notes=notes or '',
        )
        
        # Compounder forwards to auditor (stays in verification queue)
        # Auditor forwards to authority
        if is_compounder:
            claim.status = AUDITOR_STATUS_VERIFICATION_PENDING
            log_action = 'COMPOUNDER_CLAIM_FORWARDED_TO_AUDITOR'
            to_status = AUDITOR_STATUS_VERIFICATION_PENDING
        else:
            claim.status = AUDITOR_STATUS_AUTHORITY_PENDING
            log_action = 'AUDITOR_CLAIM_FORWARDED'
            to_status = AUDITOR_STATUS_AUTHORITY_PENDING
        
        claim.updated_by = request_user
        claim.save(update_fields=['status', 'updated_by'])

        _audit_reimbursement_action(
            claim,
            request_user,
            log_action,
            {
                'claim_id': claim.id,
                'from_status': 'submitted' if is_compounder else AUDITOR_STATUS_VERIFICATION_PENDING,
                'to_status': to_status,
                'notes': notes or '',
            },
        )

    return {
        'claim_id': claim.id,
        'status': claim.status,
        'action': 'forward',
        'updated_by': request_user.username,
        'updated_at': log.timestamp.isoformat(),
    }


def rejectClaimService(claim_id, notes, request_user):
    _ensure_auditor_access(request_user)
    claim = _get_claim_or_raise(claim_id)

    if claim.status in ['rejected', 'reimbursed']:
        raise PHCStaffError(f'Claim is already {claim.status}')

    with transaction.atomic():
        log = ReimbursementProcessingLog.objects.create(
            claim=claim,
            action='rejected',
            performed_by=request_user,
            notes=notes or '',
        )
        previous_status = claim.status
        claim.status = 'rejected'
        claim.updated_by = request_user
        claim.save(update_fields=['status', 'updated_by'])

        _audit_reimbursement_action(
            claim,
            request_user,
            'AUDITOR_CLAIM_REJECTED',
            {
                'claim_id': claim.id,
                'from_status': previous_status,
                'to_status': 'rejected',
                'notes': notes or '',
            },
        )

    return {
        'claim_id': claim.id,
        'status': claim.status,
        'action': 'reject',
        'updated_by': request_user.username,
        'updated_at': log.timestamp.isoformat(),
    }


def processPaymentService(claim_id, notes, request_user, payment_reference=''):
    _ensure_auditor_access(request_user)
    claim = _get_claim_or_raise(claim_id)

    if claim.status not in ['approved', 'authority_approved', 'auditor_payment_pending']:
        raise PHCStaffError('Payment can be processed only after authority approval')

    with transaction.atomic():
        previous_status = claim.status
        claim.status = 'reimbursed'
        claim.updated_by = request_user
        claim.save(update_fields=['status', 'updated_by'])

        _audit_reimbursement_action(
            claim,
            request_user,
            'AUDITOR_PAYMENT_PROCESSED',
            {
                'claim_id': claim.id,
                'from_status': previous_status,
                'to_status': 'reimbursed',
                'notes': notes or '',
                'payment_reference': payment_reference or '',
            },
        )

    return {
        'claim_id': claim.id,
        'status': claim.status,
        'action': 'process_payment',
        'updated_by': request_user.username,
        'payment_reference': payment_reference or '',
    }


def updateClaimStatusForAuditorService(claim_id, action, notes, request_user):
    normalized_action = str(action or '').strip().lower()
    if normalized_action == 'verify':
        return verifyClaimService(claim_id=claim_id, notes=notes, request_user=request_user)
    if normalized_action == 'forward':
        return forwardClaimService(claim_id=claim_id, notes=notes, request_user=request_user)
    if normalized_action == 'reject':
        return rejectClaimService(claim_id=claim_id, notes=notes, request_user=request_user)
    raise PHCStaffError('Invalid action. Must be one of: verify, forward, reject')

def processReimbursementClaimService(claim_id, action, notes, request_user):
    """
    Staff processes reimbursement claims with BR-08 workflow:
    Employee → PHC Review → Professor Approval (if needed) → Accounts → Payment
    
    Args:
        claim_id: PHCReimbursementClaim ID
        action: 'forward_to_professor', 'forward_to_accounts', 'reject', 'return'
        notes: Processing notes
        request_user: Staff user
    
    Returns:
        dict: Claim processing record
    """
    role = resolve_phc_role(request_user)
    if role != ROLE_PHC_STAFF and not request_user.is_superuser:
        raise PHCStaffPermissionError('Only PHC staff can process reimbursement claims')
    
    valid_actions = ['forward_to_professor', 'forward_to_accounts', 'reject', 'return']
    if action not in valid_actions:
        raise PHCStaffError(f'Invalid action. Must be one of: {", ".join(valid_actions)}')
    
    try:
        claim = PHCReimbursementClaim.objects.get(id=claim_id)
    except PHCReimbursementClaim.DoesNotExist:
        raise PHCStaffError(f'Claim {claim_id} not found')
    
    with transaction.atomic():
        # Create processing log
        processing_log = ReimbursementProcessingLog.objects.create(
            claim=claim,
            action=action,
            performed_by=request_user,
            notes=notes,
        )
        
        # Update claim status based on action (BR-08: Professor approval workflow)
        if action == 'forward_to_professor':
            claim.status = 'pending_professor_approval'
            claim.requires_professor_approval = True
        elif action == 'forward_to_accounts':
            claim.status = 'pending_accounts_verification'
        elif action == 'reject':
            claim.status = 'rejected'
        elif action == 'return':
            claim.status = 'submitted'
        
        claim.updated_by = request_user
        claim.save(update_fields=['status', 'requires_professor_approval', 'updated_by'])
        
        # Audit log
        PHCAppointmentAuditLog.objects.create(
            action='reimbursement_processed',
            performed_by=request_user,
            metadata=json.dumps({'claim_id': claim_id, 'action': action, 'br': 'BR-08'})
        )
    
    return {
        'claim_id': claim.id,
        'status': claim.status,
        'action': action,
        'processed_by': request_user.username,
        'processed_at': processing_log.timestamp.isoformat(),
    }


def getReimbursementClaimsForStaffService(request_user, status_filter=None):
    """
    Get reimbursement claims for staff review
    """
    role = resolve_phc_role(request_user)
    if role != ROLE_PHC_STAFF and not request_user.is_superuser:
        raise PHCStaffPermissionError('Only PHC staff can view claims')
    
    qs = PHCReimbursementClaim.objects.select_related('user').order_by('-created_at')
    
    if status_filter:
        qs = qs.filter(status=status_filter)
    
    return [
        {
            'claim_id': claim.id,
            'user_id': claim.user.id,
            'user_name': f"{claim.user.first_name} {claim.user.last_name}",
            'amount': float(claim.amount),
            'reason': claim.reason,
            'status': claim.status,
            'created_at': claim.created_at.isoformat(),
            'updated_by': claim.updated_by.username if claim.updated_by else None,
        }
        for claim in qs
    ]


def approveProfessorReimbursementService(claim_id, action, notes, request_user):
    """
    BR-08: Professor approves reimbursement claims from pending_professor_approval status
    After professor approval, claim moves to pending_accounts_verification
    
    Args:
        claim_id: PHCReimbursementClaim ID
        action: 'approve', 'reject'
        notes: Approval notes
        request_user: Professor user
    
    Returns:
        dict: Approval record
    """
    # Only professors can approve
    if request_user.user_type != 'professor' and not request_user.is_superuser:
        raise PHCStaffPermissionError('Only professors can approve reimbursement claims')
    
    if action not in ['approve', 'reject']:
        raise PHCStaffError('Invalid action. Must be: approve, reject')
    
    try:
        claim = PHCReimbursementClaim.objects.get(id=claim_id)
    except PHCReimbursementClaim.DoesNotExist:
        raise PHCStaffError(f'Claim {claim_id} not found')
    
    if claim.status != 'pending_professor_approval':
        raise PHCStaffError('Claim is not pending professor approval')
    
    with transaction.atomic():
        if action == 'approve':
            claim.status = 'pending_accounts_verification'
            claim.professor_approved_by = request_user
        elif action == 'reject':
            claim.status = 'rejected'
        
        claim.updated_by = request_user
        claim.save(update_fields=['status', 'professor_approved_by', 'updated_by'])
        
        # Audit log
        PHCAppointmentAuditLog.objects.create(
            action='professor_reimbursement_approval',
            performed_by=request_user,
            metadata=json.dumps({'claim_id': claim_id, 'action': action, 'br': 'BR-08'})
        )
    
    return {
        'claim_id': claim.id,
        'status': claim.status,
        'action': action,
        'approved_by': request_user.username,
    }


# ===========================
# DOCTOR & INVENTORY MANAGEMENT (STAFF VIEWS)
# ===========================

def getDoctorsListForStaffService(request_user, include_inactive=False):
    """
    Get list of doctors with their current schedule and attendance
    For PHC staff management dashboard
    
    Args:
        request_user: PHC Staff user
    
    Returns:
        list: Doctors with schedule and attendance info
    """
    role = resolve_phc_role(request_user)
    if role != ROLE_PHC_STAFF and not request_user.is_superuser:
        raise PHCStaffPermissionError('Only PHC staff can view doctor management')
    
    doctors_qs = Doctor.objects.all() if include_inactive else Doctor.objects.filter(active=True)
    doctors = doctors_qs.order_by('doctor_name')
    result = []
    
    for doctor in doctors:
        # Get latest attendance status
        latest_attendance = DoctorAttendance.objects.filter(
            doctor=doctor
        ).order_by('-timestamp').first()
        
        # Get doctor's schedule
        schedules = []
        for sched in Doctors_Schedule.objects.filter(doctor_id=doctor):
            schedules.append({
                'day': sched.day,
                'from_time': sched.from_time.strftime('%H:%M') if sched.from_time else None,
                'to_time': sched.to_time.strftime('%H:%M') if sched.to_time else None,
                'room': sched.room,
            })
        
        result.append({
            'doctor_id': doctor.id,
            'doctor_name': doctor.doctor_name,
            'specialization': doctor.specialization,
            'phone': doctor.doctor_phone,
            'active': doctor.active,
            'master_schedule': schedules,
            'current_status': latest_attendance.status if latest_attendance else 'available',
            'last_status_update': latest_attendance.timestamp.isoformat() if latest_attendance else None,
        })
    
    return result


def getLowStockAlertsService(request_user):
    """
    Get all active low stock alerts
    
    Args:
        request_user: PHC Staff user
    
    Returns:
        list: Low stock alert records
    """
    role = resolve_phc_role(request_user)
    if role != ROLE_PHC_STAFF and not request_user.is_superuser:
        raise PHCStaffPermissionError('Only PHC staff can view alerts')
    
    alerts = LowStockAlert.objects.filter(
        acknowledged=False
    ).select_related('inventory__medicine').order_by('-created_at')
    
    return [
        {
            'alert_id': alert.id,
            'medicine_id': alert.inventory.medicine.id,
            'medicine_name': alert.inventory.medicine.medicine_name,
            'current_stock': alert.current_stock,
            'threshold': alert.threshold,
            'created_at': alert.created_at.isoformat(),
        }
        for alert in alerts
    ]


def acknowledgeLowStockAlertService(alert_id, request_user):
    """
    Mark a low stock alert as acknowledged/read.
    """
    role = resolve_phc_role(request_user)
    if role != ROLE_PHC_STAFF and not request_user.is_superuser:
        raise PHCStaffPermissionError('Only PHC staff can acknowledge alerts')

    try:
        alert = LowStockAlert.objects.select_related('inventory__medicine').get(id=alert_id, acknowledged=False)
    except LowStockAlert.DoesNotExist:
        raise PHCStaffError(f'Alert {alert_id} not found')

    alert.acknowledged = True
    alert.acknowledged_by = request_user
    alert.save(update_fields=['acknowledged', 'acknowledged_by'])

    return {
        'alert_id': alert.id,
        'medicine_id': alert.inventory.medicine.id,
        'medicine_name': alert.inventory.medicine.medicine_name,
        'acknowledged': alert.acknowledged,
        'acknowledged_by': request_user.username,
    }


# ===========================
# UC-13: SYSTEM REPORTS
# ===========================

def _parse_report_date(value, field_name):
    if not value:
        return None
    try:
        return datetime.date.fromisoformat(str(value))
    except (TypeError, ValueError):
        raise PHCStaffError(f'{field_name} must be in YYYY-MM-DD format')


def _normalize_report_window(from_date, to_date):
    start = _parse_report_date(from_date, 'from_date')
    end = _parse_report_date(to_date, 'to_date')

    # Default to last 30 days if range not provided.
    if not start and not end:
        end = datetime.date.today()
        start = end - datetime.timedelta(days=30)
    elif start and not end:
        end = datetime.date.today()
    elif end and not start:
        start = end - datetime.timedelta(days=30)

    if start > end:
        raise PHCStaffError('from_date must be less than or equal to to_date')

    # Guardrail to keep report query sizes reasonable.
    if (end - start).days > 366:
        raise PHCStaffError('date range cannot exceed 366 days')

    return start, end


def _build_reimbursement_report(start_date, end_date):
    rows_qs = PHCReimbursementClaim.objects.select_related('user').filter(
        created_at__date__gte=start_date,
        created_at__date__lte=end_date,
    ).order_by('-created_at')

    rows = [
        {
            'claim_id': claim.id,
            'user_name': f"{claim.user.first_name} {claim.user.last_name}".strip() or claim.user.username,
            'amount': float(claim.amount),
            'status': claim.status,
            'expense_date': claim.expense_date.isoformat() if claim.expense_date else None,
            'created_at': claim.created_at.isoformat(),
        }
        for claim in rows_qs
    ]

    status_counts = {}
    for row in rows:
        status_counts[row['status']] = status_counts.get(row['status'], 0) + 1

    total_amount = rows_qs.aggregate(total=Sum('amount')).get('total') or 0

    return {
        'summary': {
            'total_claims': len(rows),
            'total_amount': float(total_amount),
            'status_breakdown': status_counts,
        },
        'rows': rows,
    }


def _build_inventory_report(start_date, end_date):
    rows_qs = Inventory.objects.select_related('medicine').all().order_by('medicine__medicine_name')
    rows = [
        {
            'medicine_id': inv.medicine.id,
            'medicine_name': inv.medicine.medicine_name,
            'stock_quantity': inv.stock_quantity,
            'reorder_threshold': inv.reorder_threshold,
            'is_low_stock': inv.is_low_stock(),
            'last_updated': inv.last_updated.isoformat(),
        }
        for inv in rows_qs
    ]

    low_stock_count = sum(1 for row in rows if row['is_low_stock'])
    total_stock_units = sum(row['stock_quantity'] for row in rows)

    return {
        'summary': {
            'total_medicines': len(rows),
            'low_stock_medicines': low_stock_count,
            'total_stock_units': total_stock_units,
        },
        'rows': rows,
    }


def _build_appointment_report(start_date, end_date):
    rows_qs = Appointment.objects.select_related('user', 'doctor').filter(
        date__gte=start_date,
        date__lte=end_date,
    ).order_by('-date', '-time_slot')

    rows = [
        {
            'appointment_id': appt.id,
            'patient_name': f"{appt.user.first_name} {appt.user.last_name}".strip() or appt.user.username,
            'doctor_name': appt.doctor.doctor_name if appt.doctor else None,
            'date': appt.date.isoformat() if appt.date else None,
            'time_slot': appt.time_slot.strftime('%H:%M') if appt.time_slot else None,
            'status': appt.status,
        }
        for appt in rows_qs
    ]

    status_counts = {}
    for row in rows:
        status_counts[row['status']] = status_counts.get(row['status'], 0) + 1

    return {
        'summary': {
            'total_appointments': len(rows),
            'status_breakdown': status_counts,
        },
        'rows': rows,
    }


# ============================================================================
# UC-06: MANAGE PATIENT RECORDS - SERVICE FUNCTIONS
# ============================================================================

def createVisitRecordService(patient_id, visit_date, request_user):
    """
    UC-06-M2: Create new visit record for a patient
    
    Args:
        patient_id: Patient's user ID
        visit_date: Date of visit
        request_user: Compounder user performing action
    
    Returns:
        dict: Created visit record details
    
    Raises:
        PHCStaffPermissionError: If user is not PHC staff
        PHCStaffError: If patient not found or invalid input
    """
    # Verify requesting user is PHC Staff
    user_role = resolve_phc_role(request_user)
    if user_role != ROLE_PHC_STAFF:
        raise PHCStaffPermissionError('Only PHC Staff can create visit records')
    
    # Get patient user
    try:
        patient = User.objects.get(id=patient_id)
    except User.DoesNotExist:
        raise PHCStaffError(f'Patient with ID {patient_id} not found')
    
    # BR-06: Visit must link to valid patient
    try:
        medical_profile = MedicalProfile.objects.get(user=patient)
    except MedicalProfile.DoesNotExist:
        medical_profile = MedicalProfile.objects.create(user=patient)
    
    # Create visit record
    visit = Visit.objects.create(
        patient=patient,
        date=visit_date,
        doctor=None,
        status='active',
        notes='Visit created by PHC Staff'
    )
    
    # Audit log
    PHCAppointmentAuditLog.objects.create(
        action='visit_record_created',
        performed_by=request_user,
    )
    
    return {
        'visit_id': visit.id,
        'patient_id': visit.patient.id,
        'patient_name': visit.patient.get_full_name(),
        'visit_date': visit.date.isoformat() if hasattr(visit.date, 'isoformat') else str(visit.date),
        'status': visit.status,
        'created_by': request_user.get_full_name(),
        'timestamp': timezone.now().isoformat(),
    }


def addPrescriptionToVisitService(visit_id, doctor_id, medicine_details, diagnosis, notes, request_user):
    """
    UC-06-M3: Add doctor's prescription to visit record
    """
    user_role = resolve_phc_role(request_user)
    if user_role != ROLE_PHC_STAFF:
        raise PHCStaffPermissionError('Only PHC Staff can add prescriptions')
    
    try:
        visit = Visit.objects.get(id=visit_id)
    except Visit.DoesNotExist:
        raise PHCStaffError(f'Visit {visit_id} not found')
    
    try:
        doctor = Doctor.objects.get(id=doctor_id)
    except Doctor.DoesNotExist:
        raise PHCStaffError(f'Doctor {doctor_id} not found')
    
    visit.doctor = doctor
    visit.diagnosis = diagnosis
    visit.notes = notes
    visit.status = 'completed'
    visit.save()
    
    PHCAppointmentAuditLog.objects.create(
        action='prescription_added_to_visit',
        performed_by=request_user,
    )
    
    return {
        'visit_id': visit.id,
        'patient_id': visit.patient.id,
        'doctor_name': doctor.doctor_name,
        'diagnosis': visit.diagnosis,
        'visit_status': visit.status,
        'updated_by': request_user.get_full_name(),
        'timestamp': timezone.now().isoformat(),
    }


def getPatientRecordsService(patient_id, request_user):
    """
    UC-06-M1: Get complete patient medical records
    """
    user_role = resolve_phc_role(request_user)
    if user_role != ROLE_PHC_STAFF:
        raise PHCStaffPermissionError('Only PHC Staff can access patient records')
    
    try:
        patient = User.objects.get(id=patient_id)
    except User.DoesNotExist:
        raise PHCStaffError(f'Patient not found')
    
    try:
        medical_profile = MedicalProfile.objects.get(user=patient)
    except MedicalProfile.DoesNotExist:
        medical_profile = None
    
    visits = Visit.objects.filter(patient=patient).order_by('-date')
    appointments = Appointment.objects.filter(user=patient).order_by('-date')
    
    visit_data = []
    for visit in visits[:10]:
        visit_data.append({
            'visit_id': visit.id,
            'date': visit.date.isoformat() if hasattr(visit.date, 'isoformat') else str(visit.date),
            'doctor': visit.doctor.doctor_name if visit.doctor else 'N/A',
            'diagnosis': getattr(visit, 'diagnosis', ''),
            'notes': visit.notes or '',
            'status': visit.status,
        })
    
    appointment_data = []
    for appt in appointments[:10]:
        appointment_data.append({
            'appointment_id': appt.id,
            'date': appt.date.isoformat() if hasattr(appt.date, 'isoformat') else str(appt.date),
            'doctor': appt.doctor.doctor_name if appt.doctor else 'N/A',
            'status': appt.status,
        })
    
    return {
        'patient_id': patient.id,
        'patient_name': patient.get_full_name(),
        'patient_email': patient.email,
        'recent_visits': visit_data,
        'recent_appointments': appointment_data,
        'total_visits': Visit.objects.filter(patient=patient).count(),
        'total_appointments': Appointment.objects.filter(user=patient).count(),
        'accessed_by': request_user.get_full_name(),
        'timestamp': timezone.now().isoformat(),
    }


def editVisitRecordService(visit_id, diagnosis, notes, request_user):
    """
    Edit/update existing visit record
    """
    user_role = resolve_phc_role(request_user)
    if user_role != ROLE_PHC_STAFF:
        raise PHCStaffPermissionError('Only PHC Staff can edit visit records')
    
    try:
        visit = Visit.objects.get(id=visit_id)
    except Visit.DoesNotExist:
        raise PHCStaffError(f'Visit {visit_id} not found')
    
    visit.diagnosis = diagnosis
    visit.notes = notes
    visit.save()
    
    PHCAppointmentAuditLog.objects.create(
        action='visit_record_edited',
        performed_by=request_user,
    )
    
    return {
        'visit_id': visit.id,
        'patient_id': visit.patient.id,
        'diagnosis': visit.diagnosis,
        'notes': visit.notes,
        'updated_by': request_user.get_full_name(),
        'timestamp': timezone.now().isoformat(),
    }


# ============================================================================
# UC-13: GENERATE SYSTEM REPORTS
# ============================================================================

def generateOperationalReportService(start_date, end_date, request_user):
    """
    Generate operational statistics report for given date range
    BR-03: Only phc_staff can access
    
    Args:
        start_date (str): ISO format date string
        end_date (str): ISO format date string
        request_user: Django User object
    
    Returns:
        dict: Report data with operational metrics
    """
    if not resolve_phc_role(request_user) == ROLE_PHC_STAFF:
        raise PHCStaffPermissionError("Only PHC staff can generate reports")
    
    start = datetime.datetime.fromisoformat(start_date)
    end = datetime.datetime.fromisoformat(end_date)
    
    # Staff attendance metrics
    attendance_logs = PHCAppointmentAuditLog.objects.filter(
        timestamp__gte=start, 
        timestamp__lte=end,
        action='attendance_marked'
    ).count()
    
    # Ambulance utilization
    ambulance_journeys = AmbulanceLog.objects.filter(
        created_at__gte=start,
        created_at__lte=end,
        status='completed'
    ).count()
    
    # Total distance traveled
    total_distance = AmbulanceLog.objects.filter(
        created_at__gte=start,
        created_at__lte=end
    ).aggregate(Sum('distance_km'))['distance_km__sum'] or 0
    
    # Doctor availability
    doctor_count = Doctor.objects.filter(is_active=True).count()
    
    # Visit statistics
    visits_count = Visit.objects.filter(
        created_at__gte=start,
        created_at__lte=end
    ).count()
    
    # Audit logs summary
    total_actions = PHCAppointmentAuditLog.objects.filter(
        timestamp__gte=start,
        timestamp__lte=end
    ).count()
    
    PHCAppointmentAuditLog.objects.create(
        action='report_generated',
        performed_by=request_user,
    )
    
    return {
        'report_type': 'operational',
        'period': {
            'start_date': start_date,
            'end_date': end_date
        },
        'metrics': {
            'attendance_logs': attendance_logs,
            'ambulance_journeys': ambulance_journeys,
            'total_distance_km': float(total_distance),
            'active_doctors': doctor_count,
            'patient_visits': visits_count,
            'total_actions_logged': total_actions,
        },
        'generated_at': timezone.now().isoformat(),
        'generated_by': request_user.get_full_name(),
    }


def generateFinancialReportService(start_date, end_date, request_user):
    """
    Generate financial/reimbursement report for given date range
    BR-03: Only phc_staff can access
    
    Args:
        start_date (str): ISO format date string
        end_date (str): ISO format date string
        request_user: Django User object
    
    Returns:
        dict: Report data with financial metrics
    """
    if not resolve_phc_role(request_user) == ROLE_PHC_STAFF:
        raise PHCStaffPermissionError("Only PHC staff can generate reports")
    
    start = datetime.datetime.fromisoformat(start_date)
    end = datetime.datetime.fromisoformat(end_date)
    
    # Reimbursement claims
    total_claims = PHCReimbursementClaim.objects.filter(
        submitted_at__gte=start,
        submitted_at__lte=end
    ).count()
    
    approved_claims = PHCReimbursementClaim.objects.filter(
        submitted_at__gte=start,
        submitted_at__lte=end,
        status='approved'
    ).count()
    
    # Total amount claimed and approved
    total_amount_claimed = PHCReimbursementClaim.objects.filter(
        submitted_at__gte=start,
        submitted_at__lte=end
    ).aggregate(total=Sum('amount_claimed'))['total'] or 0
    
    approved_amount = PHCReimbursementClaim.objects.filter(
        submitted_at__gte=start,
        submitted_at__lte=end,
        status='approved'
    ).aggregate(total=Sum('amount_claimed'))['total'] or 0
    
    # Rejection rate
    rejected_claims = total_claims - approved_claims
    rejection_rate = (rejected_claims / total_claims * 100) if total_claims > 0 else 0
    
    PHCAppointmentAuditLog.objects.create(
        action='report_generated',
        performed_by=request_user,
    )
    
    return {
        'report_type': 'financial',
        'period': {
            'start_date': start_date,
            'end_date': end_date
        },
        'metrics': {
            'total_claims_submitted': total_claims,
            'approved_claims': approved_claims,
            'rejected_claims': rejected_claims,
            'total_amount_claimed': float(total_amount_claimed),
            'total_amount_approved': float(approved_amount),
            'rejection_rate_percent': round(rejection_rate, 2),
            'approval_rate_percent': round(100 - rejection_rate, 2),
        },
        'generated_at': timezone.now().isoformat(),
        'generated_by': request_user.get_full_name(),
    }


def generateInventoryReportService(start_date, end_date, request_user):
    """
    Generate inventory status and utilization report
    BR-03: Only phc_staff can access
    
    Args:
        start_date (str): ISO format date string
        end_date (str): ISO format date string
        request_user: Django User object
    
    Returns:
        dict: Report data with inventory metrics
    """
    if not resolve_phc_role(request_user) == ROLE_PHC_STAFF:
        raise PHCStaffPermissionError("Only PHC staff can generate reports")
    
    start = datetime.datetime.fromisoformat(start_date)
    end = datetime.datetime.fromisoformat(end_date)
    
    # Inventory statistics
    total_items = All_Medicine.objects.all().count()
    low_stock_alerts = LowStockAlert.objects.filter(
        created_at__gte=start,
        created_at__lte=end
    ).count()
    
    # Total requisitions
    total_requisitions = Requisition.objects.filter(
        created_at__gte=start,
        created_at__lte=end
    ).count()
    
    fulfilled_requisitions = Requisition.objects.filter(
        created_at__gte=start,
        created_at__lte=end,
        status='fulfilled'
    ).count()
    
    # Inventory transactions
    transactions_count = InventoryTransaction.objects.filter(
        timestamp__gte=start,
        timestamp__lte=end
    ).count()
    
    # Current inventory value
    total_units = All_Medicine.objects.aggregate(
        total=Sum('quantity'))['total'] or 0
    
    PHCAppointmentAuditLog.objects.create(
        action='report_generated',
        performed_by=request_user,
    )
    
    return {
        'report_type': 'inventory',
        'period': {
            'start_date': start_date,
            'end_date': end_date
        },
        'metrics': {
            'total_medicine_items': total_items,
            'current_total_units': int(total_units),
            'low_stock_alerts_triggered': low_stock_alerts,
            'total_requisitions': total_requisitions,
            'fulfilled_requisitions': fulfilled_requisitions,
            'pending_requisitions': total_requisitions - fulfilled_requisitions,
            'inventory_transactions': transactions_count,
        },
        'generated_at': timezone.now().isoformat(),
        'generated_by': request_user.get_full_name(),
    }


def generatePatientCareReportService(start_date, end_date, request_user):
    """
    Generate patient care statistics and trends report
    BR-03: Only phc_staff can access
    
    Args:
        start_date (str): ISO format date string
        end_date (str): ISO format date string
        request_user: Django User object
    
    Returns:
        dict: Report data with patient care metrics
    """
    if not resolve_phc_role(request_user) == ROLE_PHC_STAFF:
        raise PHCStaffPermissionError("Only PHC staff can generate reports")
    
    start = datetime.datetime.fromisoformat(start_date)
    end = datetime.datetime.fromisoformat(end_date)
    
    # Visit statistics
    total_visits = Visit.objects.filter(
        created_at__gte=start,
        created_at__lte=end
    ).count()
    
    # Appointment statistics
    completed_appointments = Appointment.objects.filter(
        appointment_date__gte=start.date(),
        appointment_date__lte=end.date(),
        status='completed'
    ).count()
    
    cancelled_appointments = Appointment.objects.filter(
        appointment_date__gte=start.date(),
        appointment_date__lte=end.date(),
        status='cancelled'
    ).count()
    
    # Prescription data
    visits_with_prescriptions = Visit.objects.filter(
        created_at__gte=start,
        created_at__lte=end,
        Medical_Problem__isnull=False
    ).count()
    
    # Patient count
    unique_patients = Visit.objects.filter(
        created_at__gte=start,
        created_at__lte=end
    ).values('patient').distinct().count()
    
    # Doctor activity
    doctors_active = Doctor.objects.filter(is_active=True).count()
    
    PHCAppointmentAuditLog.objects.create(
        action='report_generated',
        performed_by=request_user,
    )
    
    return {
        'report_type': 'patient_care',
        'period': {
            'start_date': start_date,
            'end_date': end_date
        },
        'metrics': {
            'total_visits': total_visits,
            'completed_appointments': completed_appointments,
            'cancelled_appointments': cancelled_appointments,
            'visits_with_prescriptions': visits_with_prescriptions,
            'unique_patients_served': unique_patients,
            'active_doctors': doctors_active,
            'average_visits_per_doctor': round(total_visits / doctors_active, 2) if doctors_active > 0 else 0,
        },
        'generated_at': timezone.now().isoformat(),
        'generated_by': request_user.get_full_name(),
    }


def generateAuditReportService(start_date, end_date, request_user):
    """
    Generate system audit trail and compliance report
    BR-03: Only phc_staff can access
    BR-09: All staff operations must be audited
    
    Args:
        start_date (str): ISO format date string
        end_date (str): ISO format date string
        request_user: Django User object
    
    Returns:
        dict: Report data with audit metrics
    """
    if not resolve_phc_role(request_user) == ROLE_PHC_STAFF:
        raise PHCStaffPermissionError("Only PHC staff can generate reports")
    
    start = datetime.datetime.fromisoformat(start_date)
    end = datetime.datetime.fromisoformat(end_date)
    
    # Audit log statistics
    total_audit_logs = PHCAppointmentAuditLog.objects.filter(
        timestamp__gte=start,
        timestamp__lte=end
    ).count()
    
    # Action breakdown
    actions = PHCAppointmentAuditLog.objects.filter(
        timestamp__gte=start,
        timestamp__lte=end
    ).values('action').annotate(count=Sum('id'))
    
    action_breakdown = {record['action']: record['count'] for record in actions}
    
    # Reimbursement audit logs
    reimbursement_audits = PHCReimbursementAuditLog.objects.filter(
        timestamp__gte=start,
        timestamp__lte=end
    ).count()
    
    # Processing logs
    processing_logs = ReimbursementProcessingLog.objects.filter(
        log_date__gte=start.date(),
        log_date__lte=end.date()
    ).count()
    
    PHCAppointmentAuditLog.objects.create(
        action='report_generated',
        performed_by=request_user,
    )
    
    return {
        'report_type': 'audit',
        'period': {
            'start_date': start_date,
            'end_date': end_date
        },
        'metrics': {
            'total_audit_entries': total_audit_logs,
            'action_breakdown': action_breakdown,
            'reimbursement_audit_entries': reimbursement_audits,
            'processing_log_entries': processing_logs,
            'compliance_status': 'Compliant' if total_audit_logs > 0 else 'No activity',
        },
        'generated_at': timezone.now().isoformat(),
        'generated_by': request_user.get_full_name(),
    }


def getAvailableReportsService(request_user):
    """
    Get list of available report types that user can generate
    BR-03: Only phc_staff can access
    
    Args:
        request_user: Django User object
    
    Returns:
        list: Available report types with descriptions
    """
    if not resolve_phc_role(request_user) == ROLE_PHC_STAFF:
        raise PHCStaffPermissionError("Only PHC staff can access reports")
    
    reports = [
        {
            'type': 'operational',
            'name': 'Operational Report',
            'description': 'Staff attendance, ambulance usage, doctor activity',
            'metrics': ['attendance_logs', 'ambulance_journeys', 'distance_traveled', 'patient_visits']
        },
        {
            'type': 'financial',
            'name': 'Financial Report',
            'description': 'Reimbursement claims, approvals, rejections',
            'metrics': ['claims_submitted', 'approved_amount', 'rejection_rate']
        },
        {
            'type': 'inventory',
            'name': 'Inventory Report',
            'description': 'Stock levels, requisitions, low-stock alerts',
            'metrics': ['medicine_items', 'stock_levels', 'requisitions', 'transactions']
        },
        {
            'type': 'patient_care',
            'name': 'Patient Care Report',
            'description': 'Visits, appointments, prescriptions, patient demographics',
            'metrics': ['visits', 'appointments', 'prescriptions', 'unique_patients']
        },
        {
            'type': 'audit',
            'name': 'Audit Report',
            'description': 'System activity logs, compliance, processing history',
            'metrics': ['audit_entries', 'action_breakdown', 'compliance_status']
        },
    ]
    
    return reports
# UC-11: LOG AMBULANCE USAGE - SERVICE FUNCTIONS
# ============================================================================

def createAmbulanceLogService(patient_name, pickup_location, destination, status, 
                             request_user, start_time=None, end_time=None, 
                             start_odometer=None, end_odometer=None, notes=''):
    """
    UC-11: Create a new ambulance usage log entry.
    """
    # BR-001: Authentication & BR-003: Role-based access
    role = resolve_phc_role(request_user)
    if role != ROLE_PHC_STAFF and not request_user.is_superuser:
        raise PHCStaffPermissionError('Only PHC staff can log ambulance usage')
    
    # Validate required fields
    if not patient_name or not patient_name.strip():
        raise PHCStaffError('Patient name is required')
    if not pickup_location or not pickup_location.strip():
        raise PHCStaffError('Pickup location is required')
    if not destination or not destination.strip():
        raise PHCStaffError('Destination is required')
    
    # Set default times if not provided
    if not start_time:
        start_time = timezone.now()
    if not end_time and status == 'completed':
        end_time = timezone.now()
    
    # Create ambulance log entry
    ambulance_log = AmbulanceLog.objects.create(
        patient_name=patient_name.strip(),
        pickup_location=pickup_location.strip(),
        destination=destination.strip(),
        status=status,
        log_created_by=request_user,
        notes=notes.strip() if notes else '',
        requested_at=start_time,
        completed_at=end_time if status == 'completed' else None,
    )
    
    # BR-009: Audit trail
    PHCAppointmentAuditLog.objects.create(
        action='ambulance_log_created',
        performed_by=request_user,
    )
    
    return {
        'ambulance_log_id': ambulance_log.id,
        'patient_name': ambulance_log.patient_name,
        'pickup_location': ambulance_log.pickup_location,
        'destination': ambulance_log.destination,
        'status': ambulance_log.status,
        'logged_by': request_user.username,
        'created_at': timezone.now().isoformat(),
    }


def getAmbulanceLogsService(request_user, filters=None):
    """
    UC-11: Retrieve ambulance usage logs with optional filtering.
    """
    # BR-003: Role-based access
    role = resolve_phc_role(request_user)
    if role != ROLE_PHC_STAFF and not request_user.is_superuser:
        raise PHCStaffPermissionError('Only PHC staff can view ambulance logs')
    
    filters = filters or {}
    query = AmbulanceLog.objects.all().order_by('-requested_at')
    
    if filters.get('status'):
        query = query.filter(status=filters['status'])
    
    if filters.get('patient_name'):
        patient_name = filters['patient_name'].strip()
        from django.db.models import Q
        query = query.filter(Q(patient_name__icontains=patient_name))
    
    if filters.get('date_from'):
        date_from = filters['date_from']
        if isinstance(date_from, str):
            from datetime import datetime
            date_from = datetime.fromisoformat(date_from).replace(hour=0, minute=0, second=0)
        query = query.filter(requested_at__gte=date_from)
    
    if filters.get('date_to'):
        date_to = filters['date_to']
        if isinstance(date_to, str):
            from datetime import datetime
            date_to = datetime.fromisoformat(date_to).replace(hour=23, minute=59, second=59)
        query = query.filter(requested_at__lte=date_to)
    
    limit = min(int(filters.get('limit', 50)), 1000)
    total_count = query.count()
    logs = query[:limit]
    
    serialized_logs = []
    for log in logs:
        serialized_logs.append({
            'log_id': log.id,
            'patient_name': log.patient_name,
            'pickup_location': log.pickup_location,
            'destination': log.destination,
            'status': log.status,
            'requested_at': log.requested_at.isoformat() if log.requested_at else None,
            'completed_at': log.completed_at.isoformat() if log.completed_at else None,
            'logged_by': log.log_created_by.username if log.log_created_by else 'Unknown',
        })
    
    return {
        'total_count': total_count,
        'returned_count': len(serialized_logs),
        'limit': limit,
        'logs': serialized_logs,
    }


def getAmbulanceLogDetailService(ambulance_log_id, request_user):
    """
    UC-11: Get detailed information about a specific ambulance log.
    """
    role = resolve_phc_role(request_user)
    if role != ROLE_PHC_STAFF and not request_user.is_superuser:
        raise PHCStaffPermissionError('Access denied')
    
    try:
        log = AmbulanceLog.objects.get(id=ambulance_log_id)
    except AmbulanceLog.DoesNotExist:
        raise PHCStaffError(f'Ambulance log with ID {ambulance_log_id} not found')
    
    return {
        'log_id': log.id,
        'patient_name': log.patient_name,
        'pickup_location': log.pickup_location,
        'destination': log.destination,
        'status': log.status,
        'requested_at': log.requested_at.isoformat() if log.requested_at else None,
        'completed_at': log.completed_at.isoformat() if log.completed_at else None,
        'logged_by': log.log_created_by.username if log.log_created_by else 'Unknown',
    }


def updateAmbulanceLogService(ambulance_log_id, request_user, status=None, notes=None, 
                             end_time=None, end_odometer=None):
    """
    UC-11: Update an existing ambulance log entry.
    """
    role = resolve_phc_role(request_user)
    if role != ROLE_PHC_STAFF and not request_user.is_superuser:
        raise PHCStaffPermissionError('Only PHC staff can update ambulance logs')
    
    try:
        log = AmbulanceLog.objects.get(id=ambulance_log_id)
    except AmbulanceLog.DoesNotExist:
        raise PHCStaffError(f'Ambulance log with ID {ambulance_log_id} not found')
    
    valid_statuses = ['requested', 'in_transit', 'arrived', 'completed', 'cancelled']
    if status and status not in valid_statuses:
        raise PHCStaffError(f'Invalid status: {status}')
    
    if status:
        log.status = status
    
    if end_time:
        log.completed_at = end_time
    
    if notes:
        existing_notes = log.notes or ''
        log.notes = f"{existing_notes}\n[Updated] {notes}".strip()
    
    log.save()
    
    # BR-009: Audit trail
    PHCAppointmentAuditLog.objects.create(
        action='ambulance_log_updated',
        performed_by=request_user,
    )
    
    return {
        'ambulance_log_id': log.id,
        'patient_name': log.patient_name,
        'status': log.status,
        'updated_at': timezone.now().isoformat(),
    }


def completeAmbulanceJourneyService(ambulance_log_id, request_user, 
                                   end_time=None, end_odometer=None, notes=''):
    """
    UC-11: Mark ambulance journey as completed with final details.
    """
    role = resolve_phc_role(request_user)
    if role != ROLE_PHC_STAFF and not request_user.is_superuser:
        raise PHCStaffPermissionError('Only PHC staff can complete ambulance journeys')
    
    try:
        log = AmbulanceLog.objects.get(id=ambulance_log_id)
    except AmbulanceLog.DoesNotExist:
        raise PHCStaffError(f'Ambulance log not found')
    
    if not end_time:
        end_time = timezone.now()
    
    log.completed_at = end_time
    log.status = 'completed'
    log.save()
    
    # BR-009: Audit
    PHCAppointmentAuditLog.objects.create(
        action='ambulance_journey_completed',
        performed_by=request_user,
    )
    
    # Calculate metrics
    duration_minutes = None
    if log.requested_at and log.completed_at:
        duration = log.completed_at - log.requested_at
        duration_minutes = int(duration.total_seconds() / 60)
    
    return {
        'ambulance_log_id': log.id,
        'status': log.status,
        'completed_at': log.completed_at.isoformat() if log.completed_at else None,
        'duration_minutes': duration_minutes,
    }


def getAmbulanceStatsService(request_user, date_from=None, date_to=None):
    """
    UC-11: Get ambulance usage statistics for a date range.
    """
    from datetime import timedelta
    
    role = resolve_phc_role(request_user)
    if role != ROLE_PHC_STAFF and not request_user.is_superuser:
        raise PHCStaffPermissionError('Access denied')
    
    if not date_to:
        date_to = timezone.now()
    if not date_from:
        date_from = date_to - timedelta(days=30)
    
    logs = AmbulanceLog.objects.filter(
        requested_at__gte=date_from,
        requested_at__lte=date_to
    )
    
    total_journeys = logs.count()
    completed_journeys = logs.filter(status='completed').count()
    cancelled_journeys = logs.filter(status='cancelled').count()
    in_progress = logs.filter(status__in=['requested', 'in_transit', 'arrived']).count()
    
    status_breakdown = {}
    for status_val in ['requested', 'in_transit', 'arrived', 'completed', 'cancelled']:
        status_breakdown[status_val] = logs.filter(status=status_val).count()
    
    return {
        'total_journeys': total_journeys,
        'completed_journeys': completed_journeys,
        'cancelled_journeys': cancelled_journeys,
        'in_progress': in_progress,
        'completion_rate': (completed_journeys / total_journeys * 100) if total_journeys > 0 else 0,
        'status_breakdown': status_breakdown,
    }


def searchAmbulanceLogsService(request_user, search_query):
    """
    UC-11: Search ambulance logs by patient name or destination.
    """
    role = resolve_phc_role(request_user)
    if role != ROLE_PHC_STAFF and not request_user.is_superuser:
        raise PHCStaffPermissionError('Access denied')
    
    if not search_query or not search_query.strip():
        raise PHCStaffError('Search query cannot be empty')
    
    from django.db.models import Q
    
    query = AmbulanceLog.objects.filter(
        Q(patient_name__icontains=search_query) |
        Q(destination__icontains=search_query) |
        Q(pickup_location__icontains=search_query)
    ).order_by('-requested_at')
    
    results = []
    for log in query[:50]:
        results.append({
            'log_id': log.id,
            'patient_name': log.patient_name,
            'destination': log.destination,
            'status': log.status,
        })
    
    return {
        'search_query': search_query,
        'results_count': len(results),
        'logs': results,
    }


def _build_requisition_report(start_date, end_date):
    rows_qs = Requisition.objects.select_related('created_by').prefetch_related('items_list').filter(
        created_at__date__gte=start_date,
        created_at__date__lte=end_date,
    ).order_by('-created_at')

    rows = [
        {
            'requisition_id': req.id,
            'created_by': req.created_by.username if req.created_by else None,
            'status': req.status,
            'items_count': req.items_list.count(),
            'created_at': req.created_at.isoformat(),
        }
        for req in rows_qs
    ]

    status_counts = {}
    for row in rows:
        status_counts[row['status']] = status_counts.get(row['status'], 0) + 1

    return {
        'summary': {
            'total_requisitions': len(rows),
            'status_breakdown': status_counts,
        },
        'rows': rows,
    }


def getSystemReportService(request_user, report_type, from_date=None, to_date=None):
    """
    Generate PHC system reports (UC-13).
    """
    role = resolve_phc_role(request_user)
    if role != ROLE_PHC_STAFF and not request_user.is_superuser:
        raise PHCStaffPermissionError('Only PHC staff can generate reports')

    report_type = str(report_type or '').strip().lower()
    if report_type not in ['reimbursement', 'inventory', 'appointments', 'requisition']:
        raise PHCStaffError('report_type must be one of reimbursement, inventory, appointments, requisition')

    start_date, end_date = _normalize_report_window(from_date, to_date)

    if report_type == 'reimbursement':
        payload = _build_reimbursement_report(start_date, end_date)
    elif report_type == 'inventory':
        payload = _build_inventory_report(start_date, end_date)
    elif report_type == 'appointments':
        payload = _build_appointment_report(start_date, end_date)
    else:
        payload = _build_requisition_report(start_date, end_date)

    PHCAppointmentAuditLog.objects.create(
        action='report_generated',
        performed_by=request_user,
        metadata=json.dumps({
            'report_type': report_type,
            'from_date': start_date.isoformat(),
            'to_date': end_date.isoformat(),
            'rows': len(payload.get('rows', [])),
        }),
    )

    return {
        'report_type': report_type,
        'from_date': start_date.isoformat(),
        'to_date': end_date.isoformat(),
        'summary': payload.get('summary', {}),
        'rows': payload.get('rows', []),
    }


def _push_phc_notification_event(event_type, title, message, request_user, metadata=None):
    """Record a PHC notification event for UC-17/BR-11 endpoint consumption."""
    payload = {
        'event_type': event_type,
        'title': title,
        'message': message,
    }
    if metadata:
        payload['metadata'] = metadata

    PHCAppointmentAuditLog.objects.create(
        action='notification_event',
        performed_by=request_user,
        metadata=json.dumps(payload),
    )


def getPHCNotificationsService(request_user, limit=50):
    """List recent PHC notification events."""
    role = resolve_phc_role(request_user)
    if role != ROLE_PHC_STAFF and not request_user.is_superuser:
        raise PHCStaffPermissionError('Only PHC staff can view notifications')

    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = 50
    limit = max(1, min(limit, 200))

    rows = PHCAppointmentAuditLog.objects.filter(
        action='notification_event'
    ).select_related('performed_by').order_by('-timestamp')[:limit]

    notifications = []
    for row in rows:
        data = {}
        try:
            data = json.loads(row.metadata or '{}')
        except Exception:
            data = {}

        notifications.append({
            'notification_id': row.id,
            'event_type': data.get('event_type') or 'generic',
            'title': data.get('title') or 'PHC Notification',
            'message': data.get('message') or '',
            'metadata': data.get('metadata') or {},
            'created_at': row.timestamp.isoformat(),
            'created_by': row.performed_by.username if row.performed_by else None,
        })

    return notifications


def triggerPHCNotificationService(data, request_user):
    """Trigger a manual PHC notification event."""
    role = resolve_phc_role(request_user)
    if role != ROLE_PHC_STAFF and not request_user.is_superuser:
        raise PHCStaffPermissionError('Only PHC staff can trigger notifications')

    event_type = str((data or {}).get('event_type') or 'manual').strip() or 'manual'
    title = str((data or {}).get('title') or 'PHC Notification').strip()
    message = str((data or {}).get('message') or '').strip()
    metadata = (data or {}).get('metadata')
    if metadata is not None and not isinstance(metadata, dict):
        raise PHCStaffError('metadata must be an object')

    _push_phc_notification_event(
        event_type=event_type,
        title=title,
        message=message,
        request_user=request_user,
        metadata=metadata or {},
    )

    return {
        'event_type': event_type,
        'title': title,
        'message': message,
        'metadata': metadata or {},
        'triggered_by': request_user.username,
    }


# ===========================
# HELPER FUNCTIONS
# ===========================

def _get_last_appointment_date(patient_id):
    """Get date of patient's last appointment"""
    last_appt = Appointment.objects.filter(
        user_id=patient_id
    ).order_by('-date').first()
    return last_appt.date.isoformat() if last_appt else None


def _serialize_appointment(appointment):
    """Serialize Appointment model"""
    return {
        'id': appointment.id,
        'patient': appointment.user.username,
        'doctor': appointment.doctor.doctor_name,
        'date': appointment.date.isoformat(),
        'time_slot': appointment.time_slot.strftime('%H:%M'),
        'status': appointment.status,
    }


def _serialize_visit(visit):
    """Serialize Visit model"""
    return {
        'id': visit.id,
        'doctor': visit.doctor.doctor_name if visit.doctor else 'Not assigned',
        'diagnosis': visit.diagnosis[:100] + '...' if len(visit.diagnosis) > 100 else visit.diagnosis,
        'created_at': visit.created_at.isoformat(),
        'created_by': visit.created_by.username,
    }


def _serialize_medical_profile(profile):
    """Serialize MedicalProfile"""
    if not profile:
        return None
    return {
        'blood_type': profile.blood_type,
        'gender': profile.gender,
        'height': float(profile.height),
        'weight': float(profile.weight),
        'date_of_birth': profile.date_of_birth.isoformat(),
    }


def _handle_doctor_departure(doctor, request_user):
    """
    Handle doctor departure by invalidating future appointments for today
    """
    today = datetime.date.today()
    future_appointments = Appointment.objects.filter(
        doctor=doctor,
        date=today,
        status='booked',
        time_slot__gt=datetime.datetime.now().time(),
    )
    
    for appt in future_appointments:
        appt.status = 'cancelled'
        appt.save()
        PHCAppointmentAuditLog.objects.create(
            action='appointment_cancelled_doctor_departed',
            performed_by=request_user,
            appointment=appt,
        )


def _trigger_low_stock_alert(inventory):
    """Trigger a low stock alert"""
    alert, created = LowStockAlert.objects.get_or_create(
        inventory=inventory,
        acknowledged=False,
        defaults={
            'current_stock': inventory.stock_quantity,
            'threshold': inventory.reorder_threshold,
        }
    )
    return alert


# Add missing import at top
from django.db.models import Q

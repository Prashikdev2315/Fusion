import datetime
import json

from django.contrib.auth.models import User
from django.db import DatabaseError, IntegrityError, transaction
from django.utils import timezone

from applications.globals.models import ExtraInfo
from .role_guards import get_phc_roles, resolve_phc_role

from .models import Appointment, Doctor, Doctors_Schedule, PHCAppointmentAuditLog, Visit, AmbulanceLog


class PHCAppointmentError(Exception):
    pass


class PHCAppointmentPermissionError(PHCAppointmentError):
    pass


def _resolve_role(user):
    resolved = resolve_phc_role(user)
    if resolved:
        return resolved

    try:
        phc_role = getattr(getattr(user, 'phc_role_profile', None), 'role', None)
        if phc_role:
            return phc_role
    except DatabaseError:
        pass

    try:
        user_type = user.extrainfo.user_type
    except ExtraInfo.DoesNotExist:
        return None

    mapping = {
        'student': 'student',
        'faculty': 'professor',
        'compounder': 'phc_staff',
        'staff': 'accounts',
    }
    return mapping.get(user_type)


def _is_patient(user):
    roles = get_phc_roles(user)
    return 'student' in roles or 'professor' in roles


def _is_phc_staff(user):
    roles = get_phc_roles(user)
    return 'phc_staff' in roles or user.is_superuser


def _weekday_code(dt):
    # Monday=0 ... Sunday=6 to align with existing schedule constants.
    return str(dt.weekday())


def _day_to_code(value):
    """Normalize day representations to weekday code string (0-6)."""
    if value is None:
        return None

    value_str = str(value).strip()
    if value_str.isdigit() and 0 <= int(value_str) <= 6:
        return value_str

    day_map = {
        'monday': '0',
        'tuesday': '1',
        'wednesday': '2',
        'thursday': '3',
        'friday': '4',
        'saturday': '5',
        'sunday': '6',
    }
    return day_map.get(value_str.lower())


def _day_matches(schedule_day, target_date):
    target_code = _weekday_code(target_date)
    schedule_code = _day_to_code(schedule_day)
    return schedule_code == target_code


def _normalize_time_slot(value):
    if isinstance(value, datetime.time):
        return value.replace(second=0, microsecond=0)

    try:
        return datetime.datetime.strptime(value, '%H:%M').time()
    except (TypeError, ValueError):
        raise PHCAppointmentError('Invalid time_slot format. Expected HH:MM')


def _normalize_date(value):
    if isinstance(value, datetime.date):
        return value

    try:
        return datetime.datetime.strptime(value, '%Y-%m-%d').date()
    except (TypeError, ValueError):
        raise PHCAppointmentError('Invalid date format. Expected YYYY-MM-DD')


def _slot_in_schedule(doctor, date_value, time_slot):
    schedules = Doctors_Schedule.objects.select_related('doctor_id').filter(doctor_id=doctor)

    active_schedule = None
    for entry in schedules:
        if not _day_matches(entry.day, date_value):
            continue
        if entry.from_time and entry.to_time and entry.from_time <= time_slot <= entry.to_time:
            active_schedule = entry
            break

    return active_schedule


def _doctor_slot_status(doctor, date_value, time_slot):
    conflict = Appointment.objects.filter(
        doctor=doctor,
        date=date_value,
        time_slot=time_slot,
        status='booked',
    ).exists()

    return 'booked' if conflict else 'available'


def _serialize_appointment(row):
    return {
        'id': row.id,
        'patient': row.user.username,
        'patient_id': row.user.id,
        'doctor': row.doctor.doctor_name,
        'doctor_id': row.doctor.id,
        'appointment_type': 'CONSULTATION',
        'appointment_date': row.date.isoformat(),
        'appointment_time': row.time_slot.strftime('%H:%M'),
        'time_slot': row.time_slot.strftime('%H:%M'),
        'status': row.status,
        'created_at': row.created_at.isoformat(),
        'has_prescription': hasattr(row, 'visit') and row.visit is not None,
        'visit_id': row.visit.id if hasattr(row, 'visit') and row.visit else None,
    }


def _serialize_visit(row):
    return {
        'id': row.id,
        'appointment_id': row.appointment_id,
        'patient_id': row.patient_id,
        'doctor_id': row.doctor_id,
        'diagnosis': row.diagnosis,
        'prescription': row.prescription,
        'created_by': row.created_by.username,
        'created_at': row.created_at.isoformat(),
    }


def _create_audit(action, performed_by, appointment=None, visit=None, metadata=None):
    PHCAppointmentAuditLog.objects.create(
        action=action,
        performed_by=performed_by,
        appointment=appointment,
        visit=visit,
        metadata=json.dumps(metadata or {}),
    )


def getDoctorScheduleService(doctor_id=None, date_value=None):
    target_date = _normalize_date(date_value) if date_value else datetime.date.today()

    doctors_qs = Doctor.objects.filter(active=True).order_by('id')
    if doctor_id:
        doctors_qs = doctors_qs.filter(id=doctor_id)

    doctors = list(doctors_qs)
    if doctor_id and not doctors:
        raise PHCAppointmentError('Invalid doctor_id')

    now = datetime.datetime.now()
    availability = []

    for doctor in doctors:
        matching = Doctors_Schedule.objects.filter(doctor_id=doctor)
        day_schedule = None
        for entry in matching:
            if _day_matches(entry.day, target_date):
                day_schedule = entry
                break

        if not day_schedule:
            availability.append(
                {
                    'doctor_id': doctor.id,
                    'doctor_name': doctor.doctor_name,
                    'specialization': doctor.specialization,
                    'master_schedule': None,
                    'real_time_status': 'off_duty',
                    'slots': [],
                }
            )
            continue

        start_time = day_schedule.from_time
        end_time = day_schedule.to_time
        slots = []

        current = datetime.datetime.combine(target_date, start_time)
        end_dt = datetime.datetime.combine(target_date, end_time)

        while current <= end_dt:
            slot_time = current.time().replace(second=0, microsecond=0)
            slots.append(
                {
                    'time_slot': slot_time.strftime('%H:%M'),
                    'status': _doctor_slot_status(doctor, target_date, slot_time),
                }
            )
            current += datetime.timedelta(minutes=30)

        if target_date == now.date() and start_time <= now.time() <= end_time:
            rt_status = 'available'
        elif target_date < now.date():
            rt_status = 'completed'
        else:
            rt_status = 'scheduled'

        availability.append(
            {
                'doctor_id': doctor.id,
                'doctor_name': doctor.doctor_name,
                'specialization': doctor.specialization,
                'master_schedule': {
                    'day': day_schedule.day,
                    'from_time': start_time.strftime('%H:%M') if start_time else None,
                    'to_time': end_time.strftime('%H:%M') if end_time else None,
                    'room': day_schedule.room,
                },
                'real_time_status': rt_status,
                'slots': slots,
            }
        )

    return {
        'date': target_date.isoformat(),
        'availability': availability,
    }


@transaction.atomic
def createAppointmentService(data, request_user):
    if not _is_patient(request_user):
        raise PHCAppointmentPermissionError('Only student/professor can book appointments (PHC-BR-03)')

    doctor_id = data.get('doctor_id')
    date_value = data.get('date') or data.get('appointment_date')
    time_value = data.get('time_slot') or data.get('appointment_time')

    if not doctor_id or not date_value or not time_value:
        raise PHCAppointmentError('doctor_id, date, and time_slot are required (PHC-BR-15)')

    try:
        doctor = Doctor.objects.get(id=int(doctor_id), active=True)
    except (Doctor.DoesNotExist, TypeError, ValueError):
        raise PHCAppointmentError('Invalid doctor_id')

    target_date = _normalize_date(date_value)
    time_slot = _normalize_time_slot(time_value)

    schedule = _slot_in_schedule(doctor, target_date, time_slot)
    if not schedule:
        raise PHCAppointmentError('Selected time_slot is outside doctor schedule (PHC-BR-01, PHC-BR-15)')

    overlapping = Appointment.objects.filter(
        user=request_user,
        date=target_date,
        time_slot=time_slot,
        status='booked',
    ).exists()
    if overlapping:
        raise PHCAppointmentError('Overlapping appointment exists for this user (PHC-BR-15)')

    doctor_busy = Appointment.objects.filter(
        doctor=doctor,
        date=target_date,
        time_slot=time_slot,
        status='booked',
    ).exists()
    if doctor_busy:
        raise PHCAppointmentError('Selected time_slot is already booked')

    try:
        appointment = Appointment.objects.create(
            user=request_user,
            doctor=doctor,
            date=target_date,
            time_slot=time_slot,
            status='booked',
        )
    except IntegrityError:
        raise PHCAppointmentError('Unable to book appointment for selected slot')

    _create_audit(
        action='BOOK_APPOINTMENT',
        performed_by=request_user,
        appointment=appointment,
        metadata={
            'doctor_id': doctor.id,
            'date': target_date.isoformat(),
            'time_slot': time_slot.strftime('%H:%M'),
        },
    )

    return _serialize_appointment(appointment)


def getUserAppointmentsService(request_user):
    if not _is_patient(request_user):
        raise PHCAppointmentPermissionError('Only student/professor can view own appointments (PHC-BR-03)')

    rows = Appointment.objects.select_related('user', 'doctor').filter(user=request_user).order_by('-date', '-time_slot')
    return [_serialize_appointment(row) for row in rows]


def getStaffAppointmentsService(request_user):
    if not _is_phc_staff(request_user):
        raise PHCAppointmentPermissionError('Only PHC staff can view scheduled appointments (PHC-BR-03)')

    rows = Appointment.objects.select_related('user', 'doctor').prefetch_related('visit').all().order_by('-date', '-time_slot')
    return [_serialize_appointment(row) for row in rows]


@transaction.atomic
def updateStaffAppointmentStatusService(appointment_id, status, notes, request_user):
    if not _is_phc_staff(request_user):
        raise PHCAppointmentPermissionError('Only PHC staff can update appointment status (PHC-BR-03)')

    if not appointment_id:
        raise PHCAppointmentError('appointment_id is required')

    new_status = (status or '').strip().lower()
    allowed_statuses = ['booked', 'completed', 'cancelled', 'no_show', 'rescheduled']
    if new_status not in allowed_statuses:
        raise PHCAppointmentError('Invalid status. Must be one of: booked, completed, cancelled, no_show, rescheduled')

    try:
        appointment = Appointment.objects.select_related('user', 'doctor').get(id=int(appointment_id))
    except (Appointment.DoesNotExist, TypeError, ValueError):
        raise PHCAppointmentError('Invalid appointment_id')

    appointment.status = new_status
    appointment.save(update_fields=['status'])

    _create_audit(
        action='UPDATE_APPOINTMENT_STATUS',
        performed_by=request_user,
        appointment=appointment,
        metadata={
            'appointment_id': appointment.id,
            'status': new_status,
            'notes': notes or '',
        },
    )

    result = _serialize_appointment(appointment)
    result['notes'] = notes or ''
    return result


@transaction.atomic
def createVisitService(data, request_user):
    if not _is_phc_staff(request_user):
        raise PHCAppointmentPermissionError('Only PHC staff can create visit records (PHC-BR-03)')

    appointment_id = data.get('appointment_id')
    diagnosis = (data.get('diagnosis') or '').strip()
    prescription = (data.get('prescription') or '').strip()
    new_status = (data.get('status') or 'completed').strip().lower()

    if not appointment_id:
        raise PHCAppointmentError('appointment_id is required')

    if not diagnosis:
        raise PHCAppointmentError('diagnosis is required')

    if not prescription:
        raise PHCAppointmentError('prescription is required')

    if new_status not in ['completed', 'cancelled']:
        raise PHCAppointmentError("status must be 'completed' or 'cancelled'")

    try:
        appointment = Appointment.objects.select_related('user', 'doctor').get(id=int(appointment_id))
    except (Appointment.DoesNotExist, TypeError, ValueError):
        raise PHCAppointmentError('Invalid appointment_id')

    if hasattr(appointment, 'visit'):
        raise PHCAppointmentError('Visit record already exists for this appointment')

    visit = Visit.objects.create(
        appointment=appointment,
        patient=appointment.user,
        doctor=appointment.doctor,
        diagnosis=diagnosis,
        prescription=prescription,
        created_by=request_user,
    )

    appointment.status = new_status
    appointment.save(update_fields=['status'])

    _create_audit(
        action='CREATE_VISIT',
        performed_by=request_user,
        appointment=appointment,
        visit=visit,
        metadata={'status': new_status},
    )

    return _serialize_visit(visit)


def getVisitHistoryService(request_user):
    if not _is_patient(request_user):
        raise PHCAppointmentPermissionError('Only student/professor can view own visit history (PHC-BR-02, PHC-BR-03)')

    rows = Visit.objects.select_related('appointment', 'doctor', 'created_by').filter(patient=request_user).order_by('-created_at')
    return [_serialize_visit(row) for row in rows]


def _serialize_ambulance_request(row):
    return {
        'id': row.id,
        'patient_name': row.patient_name,
        'pickup_location': row.pickup_location,
        'destination': row.destination,
        'reason': row.notes,
        'status': row.status,
        'requested_at': row.requested_at.isoformat() if row.requested_at else None,
    }


def getAmbulanceRequestsService(request_user, status=None):
    """Compatibility API for GET /phc/api/ambulance/."""
    if not _is_phc_staff(request_user):
        raise PHCAppointmentPermissionError('Only PHC staff can view ambulance activity')

    qs = AmbulanceLog.objects.select_related('log_created_by').order_by('-requested_at')

    if status:
        qs = qs.filter(status=status)

    return [_serialize_ambulance_request(row) for row in qs]


@transaction.atomic
def createAmbulanceRequestService(data, request_user):
    """Compatibility API for POST /phc/api/ambulance/."""
    if not (_is_patient(request_user) or _is_phc_staff(request_user)):
        raise PHCAppointmentPermissionError('Only student/professor or PHC staff can create ambulance requests')

    pickup_location = (data.get('pickup_location') or '').strip()
    destination = (data.get('destination') or '').strip()
    reason = (data.get('reason') or '').strip()
    emergency_level = (data.get('emergency_level') or 'URGENT').strip()

    if not pickup_location:
        raise PHCAppointmentError('pickup_location is required')
    if not destination:
        raise PHCAppointmentError('destination is required')
    if not reason:
        raise PHCAppointmentError('reason is required')

    patient_name = (data.get('patient_name') or '').strip()
    if not patient_name:
        full_name = f"{request_user.first_name} {request_user.last_name}".strip()
        patient_name = full_name or request_user.username

    notes = f"{reason} | emergency_level={emergency_level}" if emergency_level else reason

    row = AmbulanceLog.objects.create(
        patient_name=patient_name,
        pickup_location=pickup_location,
        destination=destination,
        status='requested',
        log_created_by=request_user,
        notes=notes,
    )

    _create_audit(
        action='AMBULANCE_REQUEST_CREATED',
        performed_by=request_user,
        metadata={'ambulance_log_id': row.id, 'status': row.status},
    )

    return _serialize_ambulance_request(row)


@transaction.atomic
def updateAmbulanceRequestStatusService(request_id, new_status, notes, request_user):
    """Allow PHC staff to accept/update ambulance request status."""
    if not _is_phc_staff(request_user):
        raise PHCAppointmentPermissionError('Only PHC staff can update ambulance request status')

    if not request_id:
        raise PHCAppointmentError('request_id is required')

    normalized_status = (new_status or '').strip().lower()
    allowed_statuses = ['requested', 'in_transit', 'arrived', 'completed', 'cancelled']
    if normalized_status not in allowed_statuses:
        raise PHCAppointmentError('Invalid status for ambulance request')

    try:
        request_row = AmbulanceLog.objects.get(id=int(request_id))
    except (AmbulanceLog.DoesNotExist, TypeError, ValueError):
        raise PHCAppointmentError('Invalid request_id')

    request_row.status = normalized_status
    if normalized_status in ['completed', 'cancelled']:
        request_row.completed_at = timezone.now()

    if notes:
        note_text = str(notes).strip()
        if note_text:
            request_row.notes = f"{request_row.notes}\n{note_text}".strip()

    request_row.save(update_fields=['status', 'completed_at', 'notes'])

    _create_audit(
        action='AMBULANCE_REQUEST_STATUS_UPDATED',
        performed_by=request_user,
        metadata={
            'ambulance_log_id': request_row.id,
            'status': request_row.status,
        },
    )

    return _serialize_ambulance_request(request_row)

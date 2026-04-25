import json
import os
from datetime import date, timedelta

from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.db import transaction

from .models import (
    Doctor,
    Doctors_Schedule,
    PHCReimbursementAuditLog,
    PHCReimbursementClaim,
    PHCReimbursementDocument,
    Visit,
)
from .role_guards import ROLE_PROFESSOR, ROLE_STUDENT, require_role


class PHCPatientFeatureError(Exception):
    pass


ALLOWED_REIMBURSEMENT_DOC_EXTENSIONS = {'.pdf', '.png', '.jpg', '.jpeg', '.doc', '.docx'}
MAX_REIMBURSEMENT_DOC_SIZE_BYTES = 10 * 1024 * 1024
MAX_REIMBURSEMENT_SUBMISSION_WINDOW_DAYS = 30


def _serialize_doctor(doctor):
    schedules = []
    for row in Doctors_Schedule.objects.filter(doctor_id=doctor):
        schedules.append(
            {
                'day': row.day,
                'from_time': row.from_time.strftime('%H:%M') if row.from_time else None,
                'to_time': row.to_time.strftime('%H:%M') if row.to_time else None,
                'room': row.room,
            }
        )

    return {
        'doctor_id': doctor.id,
        'doctor_name': doctor.doctor_name,
        'specialization': doctor.specialization,
        'master_schedule': schedules,
        'real_time_status': 'available' if doctor.active else 'off_duty',
    }


def getDoctorsService(request_user):
    require_role([ROLE_STUDENT, ROLE_PROFESSOR])(request_user)

    doctors = Doctor.objects.filter(active=True).order_by('doctor_name')
    return [_serialize_doctor(d) for d in doctors]


def _serialize_medical_record(row):
    # Handle null doctor relationship safely
    doctor_name = None
    if row.doctor:
        doctor_name = getattr(row.doctor, 'doctor_name', 'Unknown Doctor')
    
    return {
        'visit_id': row.id,
        'appointment_id': row.appointment_id,
        'doctor_id': row.doctor_id,
        'doctor_name': doctor_name,
        'diagnosis': row.diagnosis,
        'prescription': row.prescription,
        'created_at': row.created_at.isoformat(),
    }


def getMedicalRecordsService(request_user):
    require_role([ROLE_STUDENT, ROLE_PROFESSOR])(request_user)

    rows = Visit.objects.select_related('doctor').filter(patient=request_user).order_by('-created_at')
    return [_serialize_medical_record(r) for r in rows]


def downloadMedicalRecordsService(request_user):
    records = getMedicalRecordsService(request_user)
    payload = json.dumps(records, indent=2)

    response = HttpResponse(payload, content_type='application/json')
    response['Content-Disposition'] = 'attachment; filename="medical_records.json"'
    return response


def _serialize_reimbursement_document(document, request=None):
    try:
        file_url = document.file.url if document.file else None
        # Build absolute URL if request is available
        if file_url and request:
            file_url = request.build_absolute_uri(file_url)
    except (ValueError, AttributeError):
        # Handle cases where file doesn't exist or is invalid
        file_url = None
    
    return {
        'id': document.id,
        'name': document.original_name,
        'url': file_url,
        'uploaded_at': document.uploaded_at.isoformat(),
    }


def _parse_claim_date(value):
    if not value:
        raise PHCPatientFeatureError('expense_date is required')

    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        raise PHCPatientFeatureError('expense_date must be in YYYY-MM-DD format')


def _validate_reimbursement_submission_window(expense_date):
    today = date.today()
    if expense_date > today:
        raise PHCPatientFeatureError('expense_date cannot be in the future')

    if today - expense_date > timedelta(days=MAX_REIMBURSEMENT_SUBMISSION_WINDOW_DAYS):
        raise PHCPatientFeatureError(
            f'reimbursement claims must be submitted within {MAX_REIMBURSEMENT_SUBMISSION_WINDOW_DAYS} days of the expense date'
        )


def _validate_reimbursement_documents(documents):
    if not documents:
        raise PHCPatientFeatureError('at least one supporting document is required')

    for doc in documents:
        ext = os.path.splitext(getattr(doc, 'name', ''))[1].lower()
        if ext not in ALLOWED_REIMBURSEMENT_DOC_EXTENSIONS:
            raise PHCPatientFeatureError('unsupported file format. Allowed: pdf, png, jpg, jpeg, doc, docx')
        if getattr(doc, 'size', 0) > MAX_REIMBURSEMENT_DOC_SIZE_BYTES:
            raise PHCPatientFeatureError('each document must be 10MB or smaller')


def applyReimbursementService(data, request_user, documents=None, request=None):
    from decimal import Decimal, InvalidOperation
    
    role = require_role([ROLE_PROFESSOR])(request_user)
    if role != ROLE_PROFESSOR:
        raise PermissionDenied('Access denied')

    # Validate and convert amount to Decimal
    amount_raw = data.get('amount')
    if not amount_raw and amount_raw != 0:  # Explicitly check for None and empty string
        raise PHCPatientFeatureError('amount is required')
    
    try:
        amount = Decimal(str(amount_raw).strip())
        if amount <= 0:
            raise PHCPatientFeatureError('amount must be greater than 0')
    except (InvalidOperation, ValueError):
        raise PHCPatientFeatureError('amount must be a valid number')

    reason = (data.get('reason') or '').strip()
    expense_date = _parse_claim_date(data.get('expense_date'))

    _validate_reimbursement_submission_window(expense_date)

    if not reason:
        raise PHCPatientFeatureError('reason is required')

    _validate_reimbursement_documents(documents or [])

    try:
        with transaction.atomic():
            claim = PHCReimbursementClaim.objects.create(
                user=request_user,
                amount=amount,
                reason=reason,
                expense_date=expense_date,
                status='pending_accounts_verification',
            )

            created_documents = []
            for doc in documents or []:
                created_documents.append(
                    PHCReimbursementDocument.objects.create(
                        claim=claim,
                        file=doc,
                        original_name=getattr(doc, 'name', 'supporting_document'),
                        uploaded_by=request_user,
                    )
                )

            PHCReimbursementAuditLog.objects.create(
                action='APPLY_REIMBURSEMENT',
                performed_by=request_user,
                claim=claim,
                metadata=json.dumps({'amount': str(amount), 'expense_date': expense_date.isoformat(), 'document_count': len(created_documents)}),
            )
    except Exception as e:
        raise PHCPatientFeatureError(f'Failed to create reimbursement claim: {str(e)}')

    return {
        'id': claim.id,
        'amount': str(claim.amount),
        'reason': claim.reason,
        'expense_date': claim.expense_date.isoformat() if claim.expense_date else None,
        'status': claim.status,
        'created_at': claim.created_at.isoformat(),
        'documents': [_serialize_reimbursement_document(doc, request) for doc in created_documents],
    }


def getReimbursementStatusService(request_user, request=None):
    role = require_role([ROLE_PROFESSOR])(request_user)
    if role != ROLE_PROFESSOR:
        raise PermissionDenied('Access denied')

    rows = PHCReimbursementClaim.objects.filter(user=request_user).prefetch_related('documents').order_by('-created_at')
    return [
        {
            'id': row.id,
            'amount': str(row.amount),
            'reason': row.reason,
            'expense_date': row.expense_date.isoformat() if row.expense_date else None,
            'status': row.status,
            'created_at': row.created_at.isoformat(),
            'documents': [_serialize_reimbursement_document(doc, request) for doc in row.documents.all()],
        }
        for row in rows
    ]

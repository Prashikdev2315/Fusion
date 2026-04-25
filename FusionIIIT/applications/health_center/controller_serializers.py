"""
DRF serializers for PHC controller input validation.

These are request-body / query-param validators only;
they do NOT map directly to models.
"""

from rest_framework import serializers

# ──────────────────────────────────────────────
# User Management
# ──────────────────────────────────────────────

class CreateUserRequestSerializer(serializers.Serializer):
    """Validate payload for PHC user creation."""
    role = serializers.CharField(max_length=50)
    email = serializers.EmailField()
    password = serializers.CharField(min_length=6, write_only=True)
    username = serializers.CharField(max_length=150, required=False, allow_blank=True)
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True)

    # Student fields
    registration_id = serializers.CharField(max_length=20, required=False, allow_blank=True)
    roll_number = serializers.CharField(max_length=20, required=False, allow_blank=True)
    course = serializers.CharField(max_length=100, required=False, allow_blank=True)
    year = serializers.IntegerField(required=False, allow_null=True)

    # Staff fields
    employee_id = serializers.CharField(max_length=20, required=False, allow_blank=True)
    designation = serializers.CharField(max_length=100, required=False, allow_blank=True)
    approval_level = serializers.CharField(max_length=50, required=False, allow_blank=True)


class RoleFilterQuerySerializer(serializers.Serializer):
    """Query params for filtering users by role."""
    role = serializers.CharField(max_length=50, required=False, allow_blank=True)


# ──────────────────────────────────────────────
# Appointments
# ──────────────────────────────────────────────

class AppointmentBookSerializer(serializers.Serializer):
    """Validate payload for booking an appointment."""
    doctor_id = serializers.IntegerField()
    date = serializers.DateField(required=False, allow_null=True, input_formats=['%Y-%m-%d', 'iso-8601'])
    appointment_date = serializers.DateField(required=False, allow_null=True, input_formats=['%Y-%m-%d', 'iso-8601'])
    time_slot = serializers.TimeField(required=False, allow_null=True, input_formats=['%H:%M', 'iso-8601'])
    appointment_time = serializers.TimeField(required=False, allow_null=True, input_formats=['%H:%M', 'iso-8601'])

    def validate(self, data):
        if not (data.get('date') or data.get('appointment_date')):
            raise serializers.ValidationError('date or appointment_date is required')
        if not (data.get('time_slot') or data.get('appointment_time')):
            raise serializers.ValidationError('time_slot or appointment_time is required')
        return data


class DoctorAvailabilityQuerySerializer(serializers.Serializer):
    """Query params for doctor availability lookup."""
    doctor_id = serializers.IntegerField(required=False, allow_null=True)
    date = serializers.DateField(required=False, allow_null=True, input_formats=['%Y-%m-%d', 'iso-8601'])


class StaffAppointmentStatusSerializer(serializers.Serializer):
    """Validate payload for updating appointment status."""
    appointment_id = serializers.IntegerField()
    status = serializers.CharField(max_length=30)
    notes = serializers.CharField(required=False, allow_blank=True, default='')


class VisitCreateSerializer(serializers.Serializer):
    """Validate payload for creating a visit record."""
    appointment_id = serializers.IntegerField()
    diagnosis = serializers.CharField()
    prescription = serializers.CharField()
    status = serializers.CharField(max_length=30, required=False, allow_blank=True, default='completed')


# ──────────────────────────────────────────────
# Ambulance
# ──────────────────────────────────────────────

class AmbulanceRequestCreateSerializer(serializers.Serializer):
    """Validate payload for creating an ambulance request."""
    pickup_location = serializers.CharField(max_length=255)
    destination = serializers.CharField(max_length=255)
    reason = serializers.CharField()
    patient_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    emergency_level = serializers.CharField(max_length=50, required=False, allow_blank=True, default='URGENT')


class AmbulanceStatusUpdateSerializer(serializers.Serializer):
    """Validate payload for updating ambulance request status."""
    request_id = serializers.IntegerField()
    status = serializers.CharField(max_length=30)
    notes = serializers.CharField(required=False, allow_blank=True, default='')


# ──────────────────────────────────────────────
# Patient features / Reimbursement
# ──────────────────────────────────────────────

class ReimbursementRequestSerializer(serializers.Serializer):
    """Validate payload for reimbursement application."""
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True)
    description = serializers.CharField(required=False, allow_blank=True)
    expense_date = serializers.DateField(required=False, allow_null=True, input_formats=['%Y-%m-%d', 'iso-8601'])
    hospital_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    diagnosis = serializers.CharField(required=False, allow_blank=True)
    claim_type = serializers.CharField(max_length=50, required=False, allow_blank=True)

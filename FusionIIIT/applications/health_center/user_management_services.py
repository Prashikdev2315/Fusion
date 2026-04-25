from django.contrib.auth.models import User
from django.db import IntegrityError, transaction

from applications.globals.models import Designation, ExtraInfo, HoldsDesignation

from .models import PHCUserAuditLog, PHCUserRoleProfile, StaffProfile, StudentProfile


class PHCUserManagementError(Exception):
    pass


class PHCUserManagementPermissionError(PHCUserManagementError):
    pass


ALLOWED_ROLES = {'student', 'professor', 'phc_staff', 'accounts', 'authority'}


def _normalize_role(role):
    return (role or '').strip().lower()


def _is_admin_user(user):
    if not user or not user.is_authenticated:
        return False

    if user.is_superuser or user.has_perm('auth.add_user'):
        return True

    return HoldsDesignation.objects.filter(
        working=user,
        designation__name__in=['admin', 'administrator', 'Admin', 'Administrator'],
    ).exists()


def _validate_role_and_payload(role, data):
    if role not in ALLOWED_ROLES:
        raise PHCUserManagementError('Invalid role. Allowed roles: student, professor, phc_staff, accounts, authority')

    if not data.get('email'):
        raise PHCUserManagementError('email is required')

    if not data.get('password'):
        raise PHCUserManagementError('password is required')

    if role == 'student':
        if not (data.get('registration_id') or data.get('roll_number')):
            raise PHCUserManagementError('registration_id or roll_number is required for student')
    else:
        if not data.get('employee_id'):
            raise PHCUserManagementError('employee_id is required for staff roles')

    if role in ('professor', 'phc_staff') and not data.get('designation'):
        raise PHCUserManagementError('designation is required for professor and phc_staff')

    if role == 'authority' and not data.get('approval_level'):
        raise PHCUserManagementError('approval_level is required for authority')


def _map_role_to_existing_user_type(role):
    mapping = {
        'student': 'student',
        'professor': 'faculty',
        'phc_staff': 'compounder',
        'accounts': 'staff',
        'authority': 'staff',
    }
    return mapping[role]


def _safe_extrainfo_id(data, role):
    if role == 'student':
        value = data.get('registration_id') or data.get('roll_number')
    else:
        value = data.get('employee_id')

    value = str(value).strip()
    if not value:
        raise PHCUserManagementError('Unable to derive user id for profile linkage')

    if len(value) > 20:
        raise PHCUserManagementError('registration_id/employee_id must be <= 20 characters for existing profile linkage')

    return value


def _build_username(email, data):
    if data.get('username'):
        return data.get('username').strip()
    return email.split('@')[0]


def _create_designation_for_role(user, role):
    if role == 'student':
        return

    designation, _ = Designation.objects.get_or_create(
        name=role,
        defaults={
            'full_name': role.replace('_', ' ').title(),
            'type': 'academic',
        },
    )

    HoldsDesignation.objects.get_or_create(
        user=user,
        working=user,
        designation=designation,
    )


def _serialize_user_record(user_role_profile):
    user = user_role_profile.user
    record = {
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'role': user_role_profile.role,
    }

    if user_role_profile.role == 'student' and hasattr(user, 'phc_student_profile'):
        record['student_profile'] = {
            'registration_id': user.phc_student_profile.registration_id,
            'course': user.phc_student_profile.course,
            'year': user.phc_student_profile.year,
        }

    if user_role_profile.role != 'student' and hasattr(user, 'phc_staff_profile'):
        record['staff_profile'] = {
            'employee_id': user.phc_staff_profile.employee_id,
            'designation': user.phc_staff_profile.designation,
            'role_type': user.phc_staff_profile.role_type,
            'approval_level': user.phc_staff_profile.approval_level,
        }

    return record


@transaction.atomic
def createUserService(data, performed_by):
    if not _is_admin_user(performed_by):
        raise PHCUserManagementPermissionError('Only admin can create users (PHC-BR-03)')

    role = _normalize_role(data.get('role'))
    _validate_role_and_payload(role, data)

    email = data.get('email').strip().lower()
    username = _build_username(email, data)

    if User.objects.filter(email__iexact=email).exists():
        raise PHCUserManagementError('email already exists')

    if User.objects.filter(username__iexact=username).exists():
        raise PHCUserManagementError('username already exists')

    try:
        user = User.objects.create_user(
            username=username,
            email=email,
            password=data.get('password'),
            first_name=(data.get('first_name') or '').strip(),
            last_name=(data.get('last_name') or '').strip(),
        )
    except IntegrityError:
        raise PHCUserManagementError('Unable to create user with provided credentials')

    extrainfo_id = _safe_extrainfo_id(data, role)

    if ExtraInfo.objects.filter(id=extrainfo_id).exists():
        raise PHCUserManagementError('registration_id/employee_id already exists in system')

    ExtraInfo.objects.create(
        id=extrainfo_id,
        user=user,
        user_type=_map_role_to_existing_user_type(role),
    )

    PHCUserRoleProfile.objects.create(
        user=user,
        role=role,
    )

    if role == 'student':
        StudentProfile.objects.create(
            user=user,
            registration_id=(data.get('registration_id') or data.get('roll_number')).strip(),
            course=(data.get('course') or '').strip() or None,
            year=data.get('year') or None,
        )
    else:
        StaffProfile.objects.create(
            user=user,
            employee_id=data.get('employee_id').strip(),
            designation=(data.get('designation') or '').strip() or None,
            role_type=role,
            approval_level=(data.get('approval_level') or '').strip() or None,
        )

    _create_designation_for_role(user, role)

    PHCUserAuditLog.objects.create(
        action='CREATE_USER',
        performed_by=performed_by,
        created_user=user,
    )

    return {
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'role': role,
    }


def getUsersByRoleService(role, requested_by):
    if not _is_admin_user(requested_by):
        raise PHCUserManagementPermissionError('Only admin can list users by role (PHC-BR-03)')

    normalized_role = _normalize_role(role)
    queryset = PHCUserRoleProfile.objects.select_related('user').all().order_by('user__id')

    if normalized_role:
        if normalized_role not in ALLOWED_ROLES:
            raise PHCUserManagementError('Invalid role filter. Allowed roles: student, professor, phc_staff, accounts, authority')
        queryset = queryset.filter(role=normalized_role)

    return [_serialize_user_record(entry) for entry in queryset]

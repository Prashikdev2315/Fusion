from django.core.exceptions import PermissionDenied
from django.db import DatabaseError
import logging


logger = logging.getLogger(__name__)


ROLE_STUDENT = 'student'
ROLE_PROFESSOR = 'professor'
ROLE_PHC_STAFF = 'phc_staff'
ROLE_ACCOUNTS = 'accounts'
ROLE_AUTHORITY = 'authority'


ROLE_MAP_FROM_USER_TYPE = {
    'student': ROLE_STUDENT,
    'faculty': ROLE_PROFESSOR,
    'compounder': ROLE_PHC_STAFF,
    'staff': ROLE_PHC_STAFF,  # PHC Staff users have user_type='staff'
}


def get_phc_roles(user):
    """Collect all PHC-relevant roles for a user to support multi-role accounts."""
    roles = set()

    try:
        role = getattr(getattr(user, 'phc_role_profile', None), 'role', None)
        if role:
            normalized_role = ROLE_MAP_FROM_USER_TYPE.get(str(role).strip().lower(), str(role).strip().lower())
            roles.add(normalized_role)
    except DatabaseError:
        pass

    try:
        user_type = user.extrainfo.user_type
        base_role = ROLE_MAP_FROM_USER_TYPE.get(user_type)
        if base_role:
            roles.add(base_role)
    except Exception:
        pass

    try:
        from applications.globals.models import HoldsDesignation

        designation_names = HoldsDesignation.objects.filter(working=user).values_list('designation__name', flat=True)
        for name in designation_names:
            normalized = str(name or '').strip().lower()
            if normalized == 'professor':
                roles.add(ROLE_PROFESSOR)
            elif normalized == 'compounder' or 'phc staff' in normalized:
                roles.add(ROLE_PHC_STAFF)
    except Exception:
        pass

    return roles


def resolve_phc_role(user):
    try:
        role = getattr(getattr(user, 'phc_role_profile', None), 'role', None)
        if role:
            logger.debug('PHC role resolved from role profile')
            return role
    except DatabaseError:
        pass

    try:
        user_type = user.extrainfo.user_type
        base_role = ROLE_MAP_FROM_USER_TYPE.get(user_type)
        if base_role:
            logger.debug('PHC role resolved from user type mapping')
            return base_role
    except Exception:
        logger.exception('Error reading extra info while resolving PHC role')
        pass

    # Check if user has a role-related designation (Professor, Compounder, etc)
    try:
        from applications.globals.models import HoldsDesignation

        logger.debug('Evaluating user designations for PHC role resolution')
        
        # Check for Professor designation
        has_professor_designation = HoldsDesignation.objects.filter(
            working=user,
            designation__name__iexact='Professor'
        ).exists()
        if has_professor_designation:
            logger.debug('PHC role resolved from Professor designation')
            return ROLE_PROFESSOR
        
        # Check for Compounder designation
        has_compounder_designation = HoldsDesignation.objects.filter(
            working=user,
            designation__name__iexact='Compounder'
        ).exists()
        if has_compounder_designation:
            logger.debug('PHC role resolved from Compounder designation')
            return ROLE_PHC_STAFF
        
        # Check for PHC Staff designation
        has_phc_staff_designation = HoldsDesignation.objects.filter(
            working=user,
            designation__name__icontains='PHC Staff'
        ).exists()
        if has_phc_staff_designation:
            logger.debug('PHC role resolved from PHC Staff designation')
            return ROLE_PHC_STAFF
    except Exception:
        logger.exception('Error checking designations while resolving PHC role')
        pass

    logger.info('PHC role could not be resolved for user')
    return None


def require_role(allowed_roles):
    def wrapper(user):
        roles = get_phc_roles(user)

        # Preserve caller-priority by returning first matching allowed role.
        for allowed in allowed_roles:
            if allowed in roles:
                return allowed

        role = resolve_phc_role(user)
        if role not in allowed_roles:
            raise PermissionDenied('Access denied')
        return role

    return wrapper

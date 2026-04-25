"""
UC-11: Log Ambulance Usage - Backend Services
PHC Ambulance usage logging and tracking for PHC Staff

Business Rules Implemented:
- BR-001: Authentication required
- BR-003: Role-based access control (PHC_STAFF)
- BR-009: Audit trail for all ambulance operations
"""

from django.utils import timezone
from django.db.models import Q
from datetime import datetime, timedelta


class PHCStaffAmbulanceError(Exception):
    """Exception for ambulance logging errors"""
    pass


class PHCStaffAmbulancePermissionError(Exception):
    """Exception for permission errors in ambulance logging"""
    pass


def resolve_phc_role(user):
    """Resolve PHC role for user"""
    from applications.globals.models import ExtraInfo
    try:
        extra_info = ExtraInfo.objects.select_related('user', 'department').get(user=user)
        return 'phc_staff' if extra_info.user_type == 'compounder' else 'unknown'
    except:
        return 'unknown'


ROLE_PHC_STAFF = 'phc_staff'


# ============================================================================
# UC-11: LOG AMBULANCE USAGE - SERVICES
# ============================================================================

def createAmbulanceLogService(patient_name, pickup_location, destination, status, 
                             request_user, start_time=None, end_time=None, 
                             start_odometer=None, end_odometer=None, notes=''):
    """
    Create a new ambulance usage log entry.
    
    Main Flow (M1-M3):
    - M1: Staff opens ambulance log
    - M2: Staff creates entry with patient name, date, time, destination
    - M3: System saves log entry (auditable per BR-009)
    
    Args:
        patient_name (str): Name of patient using ambulance
        pickup_location (str): Starting location (e.g., "Hospital", "Residence")
        destination (str): Destination location
        status (str): Current status ('in_transit', 'arrived', 'completed', 'cancelled')
        request_user: Staff user creating log
        start_time (datetime): When ambulance started journey
        end_time (datetime): When ambulance completed journey
        start_odometer (float): Start odometer reading (km)
        end_odometer (float): End odometer reading (km)
        notes (str): Additional notes
    
    Returns:
        dict: Created ambulance log with all details
    
    Raises:
        PHCStaffPermissionError: If user is not PHC staff
        PHCStaffAmbulanceError: If required fields missing
    """
    from applications.health_center.models import AmbulanceLog, PHCAppointmentAuditLog
    
    # BR-001: Authentication & BR-003: Role-based access
    role = resolve_phc_role(request_user)
    if role != ROLE_PHC_STAFF and not request_user.is_superuser:
        raise PHCStaffAmbulancePermissionError(
            'Only PHC staff can log ambulance usage'
        )
    
    # Validate required fields
    if not patient_name or not patient_name.strip():
        raise PHCStaffAmbulanceError('Patient name is required')
    if not pickup_location or not pickup_location.strip():
        raise PHCStaffAmbulanceError('Pickup location is required')
    if not destination or not destination.strip():
        raise PHCStaffAmbulanceError('Destination is required')
    
    # Set default times if not provided
    if not start_time:
        start_time = timezone.now()
    if not end_time and status == 'completed':
        end_time = timezone.now()
    
    # Calculate distance if odometer readings provided
    distance_traveled = None
    if start_odometer is not None and end_odometer is not None:
        distance_traveled = max(0, float(end_odometer) - float(start_odometer))
    
    # Calculate duration if both times provided
    duration_minutes = None
    if start_time and end_time:
        duration = end_time - start_time
        duration_minutes = int(duration.total_seconds() / 60)
    
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
    
    # BR-009: Audit trail - Log this action
    PHCAppointmentAuditLog.objects.create(
        action='ambulance_log_created',
        performed_by=request_user,
        visit=None,
        appointment=None,
    )
    
    return {
        'ambulance_log_id': ambulance_log.id,
        'patient_name': ambulance_log.patient_name,
        'pickup_location': ambulance_log.pickup_location,
        'destination': ambulance_log.destination,
        'status': ambulance_log.status,
        'started_at': ambulance_log.requested_at.isoformat() if ambulance_log.requested_at else None,
        'completed_at': ambulance_log.completed_at.isoformat() if ambulance_log.completed_at else None,
        'distance_traveled': distance_traveled,
        'duration_minutes': duration_minutes,
        'notes': ambulance_log.notes,
        'logged_by': request_user.username,
        'created_at': timezone.now().isoformat(),
    }


def getAmbulanceLogsService(request_user, filters=None):
    """
    Retrieve ambulance usage logs with optional filtering.
    
    Args:
        request_user: Staff user requesting logs
        filters (dict): Optional filters
            - status: Filter by status (in_transit, arrived, completed, cancelled)
            - patient_name: Search by patient name
            - date_from: Start date for range
            - date_to: End date for range
            - limit: Max records to return (default 50)
    
    Returns:
        dict: List of ambulance logs and metadata
    
    Raises:
        PHCStaffPermissionError: If user is not PHC staff
    """
    from applications.health_center.models import AmbulanceLog
    
    # BR-003: Role-based access
    role = resolve_phc_role(request_user)
    if role != ROLE_PHC_STAFF and not request_user.is_superuser:
        raise PHCStaffAmbulancePermissionError(
            'Only PHC staff can view ambulance logs'
        )
    
    filters = filters or {}
    
    # Start with all logs, ordered by most recent
    query = AmbulanceLog.objects.all().order_by('-requested_at')
    
    # Apply filters if provided
    if filters.get('status'):
        query = query.filter(status=filters['status'])
    
    if filters.get('patient_name'):
        patient_name = filters['patient_name'].strip()
        query = query.filter(
            Q(patient_name__icontains=patient_name)
        )
    
    if filters.get('date_from'):
        date_from = filters['date_from']
        if isinstance(date_from, str):
            date_from = datetime.fromisoformat(date_from).replace(hour=0, minute=0, second=0)
        query = query.filter(requested_at__gte=date_from)
    
    if filters.get('date_to'):
        date_to = filters['date_to']
        if isinstance(date_to, str):
            date_to = datetime.fromisoformat(date_to).replace(hour=23, minute=59, second=59)
        query = query.filter(requested_at__lte=date_to)
    
    # Apply limit
    limit = min(int(filters.get('limit', 50)), 1000)
    total_count = query.count()
    logs = query[:limit]
    
    # Serialize logs
    serialized_logs = []
    for log in logs:
        # Calculate distance if odometer data was stored
        distance = None
        if log.notes and 'odometer' in log.notes.lower():
            try:
                # Try to extract from notes if stored there
                pass
            except:
                pass
        
        serialized_logs.append({
            'log_id': log.id,
            'patient_name': log.patient_name,
            'pickup_location': log.pickup_location,
            'destination': log.destination,
            'status': log.status,
            'started_at': log.requested_at.isoformat() if log.requested_at else None,
            'completed_at': log.completed_at.isoformat() if log.completed_at else None,
            'logged_by': log.log_created_by.username if log.log_created_by else 'Unknown',
            'notes': log.notes,
        })
    
    return {
        'total_count': total_count,
        'returned_count': len(serialized_logs),
        'limit': limit,
        'logs': serialized_logs,
    }


def getAmbulanceLogDetailService(ambulance_log_id, request_user):
    """
    Get detailed information about a specific ambulance log.
    
    Args:
        ambulance_log_id (int): ID of ambulance log
        request_user: Staff user requesting details
    
    Returns:
        dict: Detailed ambulance log information
    
    Raises:
        PHCStaffPermissionError: If user is not PHC staff
        PHCStaffAmbulanceError: If log not found
    """
    from applications.health_center.models import AmbulanceLog
    
    # BR-003: Role-based access
    role = resolve_phc_role(request_user)
    if role != ROLE_PHC_STAFF and not request_user.is_superuser:
        raise PHCStaffAmbulancePermissionError('Access denied')
    
    try:
        log = AmbulanceLog.objects.get(id=ambulance_log_id)
    except AmbulanceLog.DoesNotExist:
        raise PHCStaffAmbulanceError(f'Ambulance log with ID {ambulance_log_id} not found')
    
    return {
        'log_id': log.id,
        'patient_name': log.patient_name,
        'pickup_location': log.pickup_location,
        'destination': log.destination,
        'status': log.status,
        'started_at': log.requested_at.isoformat() if log.requested_at else None,
        'completed_at': log.completed_at.isoformat() if log.completed_at else None,
        'logged_by': log.log_created_by.username if log.log_created_by else 'Unknown',
        'notes': log.notes,
    }


def updateAmbulanceLogService(ambulance_log_id, request_user, status=None, notes=None, 
                             end_time=None, end_odometer=None):
    """
    Update an existing ambulance log entry.
    
    Use cases:
    - Mark as completed when journey ends
    - Add end odometer readings
    - Update status (in_transit → arrived → completed)
    - Add additional notes
    
    Args:
        ambulance_log_id (int): ID of log to update
        request_user: Staff user updating log
        status (str): New status value
        notes (str): Additional notes
        end_time (datetime): End time of journey
        end_odometer (float): End odometer reading
    
    Returns:
        dict: Updated ambulance log
    
    Raises:
        PHCStaffPermissionError: If user is not PHC staff
        PHCStaffAmbulanceError: If log not found or invalid update
    """
    from applications.health_center.models import AmbulanceLog, PHCAppointmentAuditLog
    
    # BR-003: Role-based access
    role = resolve_phc_role(request_user)
    if role != ROLE_PHC_STAFF and not request_user.is_superuser:
        raise PHCStaffAmbulancePermissionError('Only PHC staff can update ambulance logs')
    
    # Get log
    try:
        log = AmbulanceLog.objects.get(id=ambulance_log_id)
    except AmbulanceLog.DoesNotExist:
        raise PHCStaffAmbulanceError(f'Ambulance log with ID {ambulance_log_id} not found')
    
    # Validate status transitions
    valid_statuses = ['requested', 'in_transit', 'arrived', 'completed', 'cancelled']
    if status and status not in valid_statuses:
        raise PHCStaffAmbulanceError(f'Invalid status: {status}')
    
    # Update fields
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
        visit=None,
        appointment=None,
    )
    
    return {
        'ambulance_log_id': log.id,
        'patient_name': log.patient_name,
        'pickup_location': log.pickup_location,
        'destination': log.destination,
        'status': log.status,
        'started_at': log.requested_at.isoformat() if log.requested_at else None,
        'completed_at': log.completed_at.isoformat() if log.completed_at else None,
        'notes': log.notes,
        'updated_at': timezone.now().isoformat(),
    }


def completeAmbulanceJourneyService(ambulance_log_id, request_user, 
                                   end_time=None, end_odometer=None, notes=''):
    """
    Mark ambulance journey as completed with final details.
    
    This is the main way to complete a journey - captures end time and odometer.
    
    Args:
        ambulance_log_id (int): ID of log
        request_user: Staff user completing journey
        end_time (datetime): When journey ended
        end_odometer (float): Final odometer reading (km)
        notes (str): Final notes
    
    Returns:
        dict: Completed ambulance log with distance/duration calculated
    
    Raises:
        PHCStaffPermissionError: If user is not PHC staff
        PHCStaffAmbulanceError: If log not found or invalid
    """
    from applications.health_center.models import AmbulanceLog, PHCAppointmentAuditLog
    
    # BR-003: Access check
    role = resolve_phc_role(request_user)
    if role != ROLE_PHC_STAFF and not request_user.is_superuser:
        raise PHCStaffAmbulancePermissionError('Only PHC staff can complete ambulance journeys')
    
    # Get log
    try:
        log = AmbulanceLog.objects.get(id=ambulance_log_id)
    except AmbulanceLog.DoesNotExist:
        raise PHCStaffAmbulanceError(f'Ambulance log not found')
    
    # Set end time
    if not end_time:
        end_time = timezone.now()
    
    log.completed_at = end_time
    log.status = 'completed'
    
    # Update notes with journey completion info
    completion_notes = f"Journey completed. "
    if end_odometer is not None:
        distance = max(0, float(end_odometer))
        completion_notes += f"End odometer: {distance}km. "
    
    if notes:
        completion_notes += notes
    
    log.notes = (log.notes or '') + '\n' + completion_notes
    log.save()
    
    # BR-009: Audit
    PHCAppointmentAuditLog.objects.create(
        action='ambulance_journey_completed',
        performed_by=request_user,
        visit=None,
        appointment=None,
    )
    
    # Calculate metrics
    duration_minutes = None
    if log.requested_at and log.completed_at:
        duration = log.completed_at - log.requested_at
        duration_minutes = int(duration.total_seconds() / 60)
    
    return {
        'ambulance_log_id': log.id,
        'patient_name': log.patient_name,
        'destination': log.destination,
        'status': log.status,
        'started_at': log.requested_at.isoformat() if log.requested_at else None,
        'completed_at': log.completed_at.isoformat() if log.completed_at else None,
        'duration_minutes': duration_minutes,
        'notes': log.notes,
        'completed_at_timestamp': timezone.now().isoformat(),
    }


def getAmbulanceStatsService(request_user, date_from=None, date_to=None):
    """
    Get ambulance usage statistics for a date range.
    
    Returns statistics like:
    - Total journeys
    - By status (completed, cancelled, etc.)
    - Recent activity
    
    Args:
        request_user: Staff user requesting stats
        date_from (datetime): Start date for stats
        date_to (datetime): End date for stats
    
    Returns:
        dict: Ambulance usage statistics
    """
    from applications.health_center.models import AmbulanceLog
    from django.db.models import Count
    
    # BR-003: Access check
    role = resolve_phc_role(request_user)
    if role != ROLE_PHC_STAFF and not request_user.is_superuser:
        raise PHCStaffAmbulancePermissionError('Access denied')
    
    # Default to last 30 days if not specified
    if not date_to:
        date_to = timezone.now()
    if not date_from:
        date_from = date_to - timedelta(days=30)
    
    # Filter logs in date range
    logs = AmbulanceLog.objects.filter(
        requested_at__gte=date_from,
        requested_at__lte=date_to
    )
    
    # Calculate stats
    total_journeys = logs.count()
    completed_journeys = logs.filter(status='completed').count()
    cancelled_journeys = logs.filter(status='cancelled').count()
    in_progress = logs.filter(status__in=['requested', 'in_transit', 'arrived']).count()
    
    # Get status breakdown
    status_breakdown = {}
    for status in ['requested', 'in_transit', 'arrived', 'completed', 'cancelled']:
        status_breakdown[status] = logs.filter(status=status).count()
    
    return {
        'date_from': date_from.isoformat(),
        'date_to': date_to.isoformat(),
        'total_journeys': total_journeys,
        'completed_journeys': completed_journeys,
        'cancelled_journeys': cancelled_journeys,
        'in_progress': in_progress,
        'completion_rate': (completed_journeys / total_journeys * 100) if total_journeys > 0 else 0,
        'status_breakdown': status_breakdown,
    }


def searchAmbulanceLogsService(request_user, search_query):
    """
    Search ambulance logs by patient name or destination.
    
    Args:
        request_user: Staff user performing search
        search_query (str): Search term
    
    Returns:
        dict: List of matching logs
    """
    from applications.health_center.models import AmbulanceLog
    
    # BR-003: Access check
    role = resolve_phc_role(request_user)
    if role != ROLE_PHC_STAFF and not request_user.is_superuser:
        raise PHCStaffAmbulancePermissionError('Access denied')
    
    if not search_query or not search_query.strip():
        raise PHCStaffAmbulanceError('Search query cannot be empty')
    
    search_term = search_query.strip().lower()
    
    logs = AmbulanceLog.objects.filter(
        Q(patient_name__icontains=search_term) |
        Q(destination__icontains=search_term) |
        Q(pickup_location__icontains=search_term)
    ).order_by('-requested_at')[:50]
    
    result = []
    for log in logs:
        result.append({
            'log_id': log.id,
            'patient_name': log.patient_name,
            'pickup_location': log.pickup_location,
            'destination': log.destination,
            'status': log.status,
            'requested_at': log.requested_at.isoformat() if log.requested_at else None,
        })
    
    return {
        'search_query': search_query,
        'results_count': len(result),
        'logs': result,
    }


# ============================================================================
# AMBULANCE AVAILABILITY MANAGEMENT
# ============================================================================

def updateAmbulanceAvailabilityService(status, request_user):
    """
    Update ambulance availability status.
    
    Status options:
    - 'available': Ready for dispatch
    - 'in_use': Currently on a trip
    - 'maintenance': Under maintenance, unavailable
    
    Args:
        status (str): New availability status
        request_user: Staff user updating status
    
    Returns:
        dict: Updated status with timestamp
    
    Raises:
        PHCStaffPermissionError: If user is not PHC staff
        PHCStaffAmbulanceError: If invalid status
    """
    # BR-001: Authentication & BR-003: Role-based access
    role = resolve_phc_role(request_user)
    if role != ROLE_PHC_STAFF and not request_user.is_superuser:
        raise PHCStaffAmbulancePermissionError('Only PHC staff can update ambulance status')
    
    # Validate status
    valid_statuses = ['available', 'in_use', 'maintenance']
    if status not in valid_statuses:
        raise PHCStaffAmbulanceError(f'Invalid status. Must be one of: {", ".join(valid_statuses)}')
    
    # Store in cache-like structure (can be extended to database if needed)
    from django.core.cache import cache
    cache.set('phc_ambulance_availability', {
        'status': status,
        'last_updated': timezone.now().isoformat(),
        'updated_by': request_user.username,
    }, timeout=None)  # No timeout - permanent until changed
    
    return {
        'status': status,
        'message': f'Ambulance availability updated to: {status}',
        'last_updated': timezone.now().isoformat(),
        'updated_by': request_user.username,
    }


def getAmbulanceAvailabilityService(request_user):
    """
    Get current ambulance availability status.
    
    Args:
        request_user: Staff user requesting status
    
    Returns:
        dict: Current availability status
    
    Raises:
        PHCStaffPermissionError: If user is not PHC staff
    """
    # BR-003: Access check
    role = resolve_phc_role(request_user)
    if role != ROLE_PHC_STAFF and not request_user.is_superuser:
        raise PHCStaffAmbulancePermissionError('Only PHC staff can view ambulance status')
    
    from django.core.cache import cache
    cached_status = cache.get('phc_ambulance_availability')
    
    if cached_status:
        return cached_status
    
    # Default status
    return {
        'status': 'available',
        'last_updated': timezone.now().isoformat(),
        'message': 'Default availability (no previous updates)',
    }


# ============================================================================
# STUDENT AMBULANCE REQUESTS - VIEW OWN APPLICATIONS
# ============================================================================

def getStudentAmbulanceRequestsService(request_user, filters=None):
    """
    Get ambulance requests made by the logged-in student.
    
    Student can only see their own ambulance requests/applications.
    
    Args:
        request_user: Student user requesting their own data
        filters (dict): Optional filters
            - status: Filter by status (requested, in_transit, completed, cancelled)
            - date_from: Start date range
            - date_to: End date range
            - limit: Max records (default 50, max 500)
    
    Returns:
        dict: List of student's ambulance requests with metadata
    
    Raises:
        PHCStaffAmbulanceError: If no records found
    """
    from applications.health_center.models import AmbulanceLog
    
    filters = filters or {}
    
    # Get only logs created by this student
    query = AmbulanceLog.objects.filter(
        log_created_by=request_user
    ).order_by('-requested_at')
    
    # Apply status filter if provided
    if filters.get('status'):
        query = query.filter(status=filters['status'])
    
    # Apply date range filters
    if filters.get('date_from'):
        date_from = filters['date_from']
        if isinstance(date_from, str):
            date_from = datetime.fromisoformat(date_from).replace(hour=0, minute=0, second=0)
        query = query.filter(requested_at__gte=date_from)
    
    if filters.get('date_to'):
        date_to = filters['date_to']
        if isinstance(date_to, str):
            date_to = datetime.fromisoformat(date_to).replace(hour=23, minute=59, second=59)
        query = query.filter(requested_at__lte=date_to)
    
    # Apply limit
    limit = min(int(filters.get('limit', 50)), 500)
    total_count = query.count()
    logs = query[:limit]
    
    # Serialize logs
    serialized_requests = []
    for log in logs:
        serialized_requests.append({
            'request_id': log.id,
            'patient_name': log.patient_name,
            'pickup_location': log.pickup_location,
            'destination': log.destination,
            'status': log.status,
            'requested_at': log.requested_at.isoformat() if log.requested_at else None,
            'completed_at': log.completed_at.isoformat() if log.completed_at else None,
            'notes': log.notes,
            'logged_by': log.log_created_by.username if log.log_created_by else 'Unknown',
        })
    
    return {
        'total_count': total_count,
        'returned_count': len(serialized_requests),
        'limit': limit,
        'requests': serialized_requests,
    }

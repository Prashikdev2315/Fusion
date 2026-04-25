"""
Auditor Services - UC-17: Auditor Action History
Tracks all approval/rejection actions performed by auditors on reimbursement claims
"""

from django.utils import timezone
from .models import PHCReimbursementAuditLog, PHCReimbursementClaim


class PHCReimbursementAuditError(Exception):
    """Custom exception for auditor audit operations"""
    pass


def getAuditorActionHistoryService(request_user, filters=None):
    """
    UC-17: Get all actions (approve/reject) performed by the auditor
    
    Args:
        request_user: User object (must be auditor)
        filters: Dict with optional filters
            - action: 'approved', 'rejected', 'all'
            - start_date: ISO format date
            - end_date: ISO format date
            - limit: max records (default 100, max 500)
    
    Returns:
        Dict with:
        - total_actions: Total count of actions performed by this auditor
        - approved_count: Count of approved claims
        - rejected_count: Count of rejected claims
        - returned_count: Count in this response
        - actions: List of actions with claim details
    
    Raises:
        PHCReimbursementAuditError: If access denied or filters invalid
    """
    
    filters = filters or {}
    
    # Get audit logs where this user performed actions
    audit_logs = PHCReimbursementAuditLog.objects.filter(
        performed_by=request_user
    ).select_related('claim', 'performed_by').order_by('-timestamp')
    
    # Filter by action type
    action_filter = filters.get('action', 'all')
    if action_filter == 'approved':
        audit_logs = audit_logs.filter(action='claim_approved')
    elif action_filter == 'rejected':
        audit_logs = audit_logs.filter(action='claim_rejected')
    elif action_filter == 'forwarded':
        audit_logs = audit_logs.filter(action__in=['forward_to_professor', 'forward_to_accounts'])
    
    # Filter by date range
    if filters.get('start_date'):
        try:
            start_date = timezone.datetime.fromisoformat(filters['start_date']).replace(hour=0, minute=0, second=0)
            audit_logs = audit_logs.filter(timestamp__gte=start_date)
        except (ValueError, TypeError):
            raise PHCReimbursementAuditError('Invalid start_date format. Use ISO format: YYYY-MM-DD')
    
    if filters.get('end_date'):
        try:
            end_date = timezone.datetime.fromisoformat(filters['end_date']).replace(hour=23, minute=59, second=59)
            audit_logs = audit_logs.filter(timestamp__lte=end_date)
        except (ValueError, TypeError):
            raise PHCReimbursementAuditError('Invalid end_date format. Use ISO format: YYYY-MM-DD')
    
    # Get counts before limiting
    total_actions = audit_logs.count()
    approved_count = audit_logs.filter(action='claim_approved').count()
    rejected_count = audit_logs.filter(action='claim_rejected').count()
    
    # Apply limit
    try:
        limit = min(int(filters.get('limit', 100)), 500)
    except (ValueError, TypeError):
        limit = 100
    
    limited_logs = audit_logs[:limit]
    returned_count = len(limited_logs)
    
    # Format response
    actions = []
    for log in limited_logs:
        action_dict = {
            'log_id': log.id,
            'action': log.action,
            'timestamp': log.timestamp.isoformat(),
            'claim_id': log.claim.id if log.claim else None,
            'claim_amount': str(log.claim.amount) if log.claim else None,
            'claim_reason': log.claim.reason if log.claim else None,
            'claim_status': log.claim.status if log.claim else None,
            'claim_user': log.claim.user.get_full_name() if log.claim and log.claim.user else None,
            'metadata': log.metadata,
        }
        actions.append(action_dict)
    
    return {
        'total_actions': total_actions,
        'approved_count': approved_count,
        'rejected_count': rejected_count,
        'returned_count': returned_count,
        'limit': limit,
        'actions': actions,
    }

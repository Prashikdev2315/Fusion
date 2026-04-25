"""
Auditor Controllers - UC-17: Auditor Action History
Request/response handlers for auditor endpoints
"""

from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from rest_framework.response import Response

from .auditor_services import (
    getAuditorActionHistoryService,
    PHCReimbursementAuditError,
)
from .staff_services import resolve_phc_role


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def getAuditorActionHistoryController(request):
    """
    GET /phc/auditor/action-history/
    
    Get all actions (approve/reject/forward) performed by the auditor on reimbursement claims.
    Only auditors can access this endpoint.
    
    Query Parameters:
    - action: 'all', 'approved', 'rejected', 'forwarded' (default: 'all')
    - start_date: ISO format date (YYYY-MM-DD)
    - end_date: ISO format date (YYYY-MM-DD)
    - limit: Max records to return (default 100, max 500)
    
    Response (200):
    {
        "success": true,
        "data": {
            "total_actions": 45,
            "approved_count": 30,
            "rejected_count": 15,
            "returned_count": 45,
            "limit": 100,
            "actions": [
                {
                    "log_id": 1,
                    "action": "claim_approved",
                    "timestamp": "2026-04-19T10:30:00Z",
                    "claim_id": 5,
                    "claim_amount": "5000.00",
                    "claim_reason": "Medical expense",
                    "claim_status": "pending_accounts_verification",
                    "claim_user": "John Doe",
                    "metadata": ""
                }
            ]
        }
    }
    """
    try:
        # Check if user is auditor
        phc_role = resolve_phc_role(request.user)
        normalized_role = str(request.user.extra_info.user_type or '').lower() if hasattr(request.user, 'extra_info') else ''
        is_auditor = (
            'auditor' in str(request.user.username or '').lower() or
            'accounts' in str(phc_role or '').lower() or
            'audit' in normalized_role
        )
        
        if not is_auditor:
            return Response({
                'success': False,
                'message': 'Only auditors can view action history',
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Build filters from query parameters
        filters = {}
        
        if request.query_params.get('action'):
            filters['action'] = request.query_params.get('action').strip()
        
        if request.query_params.get('start_date'):
            filters['start_date'] = request.query_params.get('start_date')
        
        if request.query_params.get('end_date'):
            filters['end_date'] = request.query_params.get('end_date')
        
        if request.query_params.get('limit'):
            filters['limit'] = request.query_params.get('limit')
        
        # Get auditor action history
        result = getAuditorActionHistoryService(request.user, filters)
        
        return Response({
            'success': True,
            'data': result,
        }, status=status.HTTP_200_OK)
    
    except PHCReimbursementAuditError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({
            'success': False,
            'message': f'Server error: {str(e)}',
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

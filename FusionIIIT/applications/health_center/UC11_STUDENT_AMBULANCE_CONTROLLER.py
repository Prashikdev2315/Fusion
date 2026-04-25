"""
UC-11: Student Ambulance Requests Controller
Endpoints for students to view their ambulance request history
"""

from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated

from .UC11_LOG_AMBULANCE_USAGE_SERVICES import (
    getStudentAmbulanceRequestsService,
    PHCStaffAmbulanceError,
)


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def getStudentAmbulanceRequestsController(request):
    """
    GET /phc/ambulance/my-requests/
    
    Get ambulance requests made by the logged-in student.
    Only shows records where the student is the applicant.
    
    Query Parameters:
    - status: Filter by status (requested, in_transit, completed, cancelled)
    - date_from: Start date (ISO format)
    - date_to: End date (ISO format)
    - limit: Max records (default 50, max 500)
    
    Example: GET /phc/ambulance/my-requests/?status=completed&limit=20
    
    Response (200):
    {
        "success": true,
        "data": {
            "total_count": 5,
            "returned_count": 5,
            "limit": 50,
            "requests": [
                {
                    "request_id": 1,
                    "patient_name": "John Doe",
                    "pickup_location": "Home",
                    "destination": "Hospital",
                    "status": "completed",
                    "requested_at": "2024-01-15T09:30:00Z",
                    "completed_at": "2024-01-15T10:15:00Z",
                    "notes": "Emergency transfer"
                }
            ]
        }
    }
    """
    try:
        # Build filters from query parameters
        filters = {}
        
        if request.query_params.get('status'):
            filters['status'] = request.query_params.get('status').strip()
        
        if request.query_params.get('date_from'):
            filters['date_from'] = request.query_params.get('date_from')
        
        if request.query_params.get('date_to'):
            filters['date_to'] = request.query_params.get('date_to')
        
        if request.query_params.get('limit'):
            filters['limit'] = request.query_params.get('limit')
        
        # Get student's ambulance requests
        result = getStudentAmbulanceRequestsService(request.user, filters)
        
        return Response({
            'success': True,
            'data': result,
        }, status=status.HTTP_200_OK)
    
    except PHCStaffAmbulanceError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({
            'success': False,
            'message': f'Server error: {str(e)}',
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

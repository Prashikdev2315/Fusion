"""
UC-11: Log Ambulance Usage - API Controllers
Endpoints for ambulance usage logging and tracking

Available Endpoints:
- POST   /phc/ambulance/logs/create/               → Create new log
- GET    /phc/ambulance/logs/                      → List all logs with filters
- GET    /phc/ambulance/logs/{log_id}/             → Get log details
- PUT    /phc/ambulance/logs/{log_id}/update/      → Update log
- PUT    /phc/ambulance/logs/{log_id}/complete/    → Complete journey
- GET    /phc/ambulance/logs/stats/                → Get statistics
- GET    /phc/ambulance/logs/search/               → Search logs
"""

from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from datetime import datetime

from .UC11_LOG_AMBULANCE_USAGE_SERVICES import (
    createAmbulanceLogService,
    getAmbulanceLogsService,
    getAmbulanceLogDetailService,
    updateAmbulanceLogService,
    completeAmbulanceJourneyService,
    getAmbulanceStatsService,
    searchAmbulanceLogsService,
    updateAmbulanceAvailabilityService,
    getAmbulanceAvailabilityService,
    PHCStaffAmbulanceError,
    PHCStaffAmbulancePermissionError,
)


# ============================================================================
# UC-11: LOG AMBULANCE USAGE - CONTROLLERS
# ============================================================================

@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def createAmbulanceLogController(request):
    """
    POST /phc/ambulance/logs/create/
    
    Create a new ambulance usage log entry.
    
    Main Flow:
    - M1: Staff opens ambulance log
    - M2: Staff creates new entry recording patient name, date, time, destination
    - M3: System saves log (auditable per PHC-BR-09)
    
    Request Body:
    {
        "patient_name": "John Doe",
        "pickup_location": "Hospital Main Gate",
        "destination": "City Medical Center",
        "status": "in_transit",
        "start_time": "2024-01-15T09:30:00Z",
        "end_time": "2024-01-15T10:15:00Z",
        "start_odometer": 1000.5,
        "end_odometer": 1025.3,
        "notes": "Routine transfer"
    }
    
    Response (201):
    {
        "success": true,
        "message": "Ambulance log created successfully",
        "data": {
            "ambulance_log_id": 1,
            "patient_name": "John Doe",
            "pickup_location": "Hospital Main Gate",
            "destination": "City Medical Center",
            "status": "in_transit",
            "started_at": "2024-01-15T09:30:00Z",
            "completed_at": "2024-01-15T10:15:00Z",
            "distance_traveled": 24.8,
            "duration_minutes": 45,
            "notes": "Routine transfer",
            "logged_by": "compounder1",
            "created_at": "2024-01-15T10:20:00Z"
        }
    }
    """
    try:
        data = request.data
        
        # Parse timestamps if provided
        start_time = None
        end_time = None
        if data.get('start_time'):
            try:
                start_time = datetime.fromisoformat(data['start_time'].replace('Z', '+00:00'))
            except:
                pass
        if data.get('end_time'):
            try:
                end_time = datetime.fromisoformat(data['end_time'].replace('Z', '+00:00'))
            except:
                pass
        
        ambulance_log = createAmbulanceLogService(
            patient_name=data.get('patient_name'),
            pickup_location=data.get('pickup_location'),
            destination=data.get('destination'),
            status=data.get('status', 'requested'),
            request_user=request.user,
            start_time=start_time,
            end_time=end_time,
            start_odometer=data.get('start_odometer'),
            end_odometer=data.get('end_odometer'),
            notes=data.get('notes', ''),
        )
        
        return Response({
            'success': True,
            'message': 'Ambulance log created successfully',
            'data': ambulance_log,
        }, status=status.HTTP_201_CREATED)
    
    except PHCStaffAmbulancePermissionError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_403_FORBIDDEN)
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


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def getAmbulanceLogsController(request):
    """
    GET /phc/ambulance/logs/
    
    Retrieve ambulance usage logs with optional filtering.
    
    Query Parameters:
    - status: Filter by status (in_transit, arrived, completed, cancelled)
    - patient_name: Search by patient name
    - date_from: Start date (ISO format)
    - date_to: End date (ISO format)
    - limit: Max records (default 50, max 1000)
    
    Example: GET /phc/ambulance/logs/?status=completed&limit=20
    
    Response (200):
    {
        "success": true,
        "data": {
            "total_count": 120,
            "returned_count": 20,
            "limit": 20,
            "logs": [
                {
                    "log_id": 1,
                    "patient_name": "John Doe",
                    "pickup_location": "Hospital",
                    "destination": "City Medical",
                    "status": "completed",
                    "started_at": "2024-01-15T09:30:00Z",
                    "completed_at": "2024-01-15T10:15:00Z",
                    "logged_by": "compounder1",
                    "notes": "Routine transfer"
                }
            ]
        }
    }
    """
    try:
        filters = {
            'status': request.query_params.get('status'),
            'patient_name': request.query_params.get('patient_name'),
            'date_from': request.query_params.get('date_from'),
            'date_to': request.query_params.get('date_to'),
            'limit': request.query_params.get('limit', 50),
        }
        
        result = getAmbulanceLogsService(request.user, filters=filters)
        
        return Response({
            'success': True,
            'data': result,
        }, status=status.HTTP_200_OK)
    
    except PHCStaffAmbulancePermissionError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_403_FORBIDDEN)
    except Exception as e:
        return Response({
            'success': False,
            'message': f'Server error: {str(e)}',
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def getAmbulanceLogDetailController(request, log_id):
    """
    GET /phc/ambulance/logs/{log_id}/
    
    Get detailed information about a specific ambulance log.
    
    Response (200):
    {
        "success": true,
        "data": {
            "log_id": 1,
            "patient_name": "John Doe",
            "pickup_location": "Hospital",
            "destination": "City Medical",
            "status": "completed",
            "started_at": "2024-01-15T09:30:00Z",
            "completed_at": "2024-01-15T10:15:00Z",
            "logged_by": "compounder1",
            "notes": "Routine transfer"
        }
    }
    """
    try:
        result = getAmbulanceLogDetailService(log_id, request.user)
        
        return Response({
            'success': True,
            'data': result,
        }, status=status.HTTP_200_OK)
    
    except PHCStaffAmbulancePermissionError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_403_FORBIDDEN)
    except PHCStaffAmbulanceError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            'success': False,
            'message': f'Server error: {str(e)}',
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def updateAmbulanceLogController(request, log_id):
    """
    PUT /phc/ambulance/logs/{log_id}/update/
    
    Update an existing ambulance log entry.
    
    Request Body:
    {
        "status": "in_transit",
        "notes": "Additional notes about journey",
        "end_time": "2024-01-15T10:15:00Z"
    }
    
    Response (200):
    {
        "success": true,
        "message": "Ambulance log updated successfully",
        "data": {...updated log...}
    }
    """
    try:
        data = request.data
        
        # Parse end_time if provided
        end_time = None
        if data.get('end_time'):
            try:
                end_time = datetime.fromisoformat(data['end_time'].replace('Z', '+00:00'))
            except:
                pass
        
        result = updateAmbulanceLogService(
            ambulance_log_id=log_id,
            request_user=request.user,
            status=data.get('status'),
            notes=data.get('notes'),
            end_time=end_time,
            end_odometer=data.get('end_odometer'),
        )
        
        return Response({
            'success': True,
            'message': 'Ambulance log updated successfully',
            'data': result,
        }, status=status.HTTP_200_OK)
    
    except PHCStaffAmbulancePermissionError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_403_FORBIDDEN)
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


@api_view(['PUT'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def completeAmbulanceJourneyController(request, log_id):
    """
    PUT /phc/ambulance/logs/{log_id}/complete/
    
    Mark ambulance journey as completed with final details.
    
    Request Body:
    {
        "end_time": "2024-01-15T10:15:00Z",
        "end_odometer": 1025.3,
        "notes": "Patient delivered safely"
    }
    
    Response (200):
    {
        "success": true,
        "message": "Ambulance journey completed",
        "data": {
            "ambulance_log_id": 1,
            "status": "completed",
            "started_at": "2024-01-15T09:30:00Z",
            "completed_at": "2024-01-15T10:15:00Z",
            "duration_minutes": 45,
            "completed_at_timestamp": "2024-01-15T10:20:00Z"
        }
    }
    """
    try:
        data = request.data
        
        # Parse end_time if provided
        end_time = None
        if data.get('end_time'):
            try:
                end_time = datetime.fromisoformat(data['end_time'].replace('Z', '+00:00'))
            except:
                pass
        
        result = completeAmbulanceJourneyService(
            ambulance_log_id=log_id,
            request_user=request.user,
            end_time=end_time,
            end_odometer=data.get('end_odometer'),
            notes=data.get('notes', ''),
        )
        
        return Response({
            'success': True,
            'message': 'Ambulance journey completed',
            'data': result,
        }, status=status.HTTP_200_OK)
    
    except PHCStaffAmbulancePermissionError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_403_FORBIDDEN)
    except PHCStaffAmbulanceError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            'success': False,
            'message': f'Server error: {str(e)}',
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def getAmbulanceStatsController(request):
    """
    GET /phc/ambulance/logs/stats/
    
    Get ambulance usage statistics.
    
    Query Parameters:
    - date_from: Start date (default: 30 days ago)
    - date_to: End date (default: today)
    
    Response (200):
    {
        "success": true,
        "data": {
            "date_from": "2024-01-01T00:00:00Z",
            "date_to": "2024-02-15T23:59:59Z",
            "total_journeys": 120,
            "completed_journeys": 115,
            "cancelled_journeys": 5,
            "in_progress": 0,
            "completion_rate": 95.83,
            "status_breakdown": {
                "completed": 115,
                "cancelled": 5,
                "in_transit": 0,
                "arrived": 0,
                "requested": 0
            }
        }
    }
    """
    try:
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')
        
        # Parse dates if provided
        if date_from:
            try:
                date_from = datetime.fromisoformat(date_from.replace('Z', '+00:00'))
            except:
                date_from = None
        
        if date_to:
            try:
                date_to = datetime.fromisoformat(date_to.replace('Z', '+00:00'))
            except:
                date_to = None
        
        result = getAmbulanceStatsService(request.user, date_from=date_from, date_to=date_to)
        
        return Response({
            'success': True,
            'data': result,
        }, status=status.HTTP_200_OK)
    
    except PHCStaffAmbulancePermissionError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_403_FORBIDDEN)
    except Exception as e:
        return Response({
            'success': False,
            'message': f'Server error: {str(e)}',
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def searchAmbulanceLogsController(request):
    """
    GET /phc/ambulance/logs/search/
    
    Search ambulance logs by patient name or destination.
    
    Query Parameters:
    - q: Search query (patient name, destination, pickup location)
    
    Example: GET /phc/ambulance/logs/search/?q=John+Doe
    
    Response (200):
    {
        "success": true,
        "data": {
            "search_query": "John Doe",
            "results_count": 5,
            "logs": [...]
        }
    }
    """
    try:
        search_query = request.query_params.get('q', '').strip()
        
        result = searchAmbulanceLogsService(request.user, search_query)
        
        return Response({
            'success': True,
            'data': result,
        }, status=status.HTTP_200_OK)
    
    except PHCStaffAmbulancePermissionError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_403_FORBIDDEN)
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


# ============================================================================
# AMBULANCE AVAILABILITY MANAGEMENT CONTROLLERS
# ============================================================================

@api_view(['POST', 'GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def ambulanceAvailabilityController(request):
    """
    POST /phc/ambulance/availability/
    Update ambulance availability status
    
    GET /phc/ambulance/availability/
    Get current ambulance availability status
    
    POST Request Body:
    {
        "status": "available"  # available, in_use, or maintenance
    }
    
    Response (200):
    {
        "success": true,
        "data": {
            "status": "available",
            "last_updated": "2024-01-15T14:30:00Z",
            "updated_by": "compounder1"
        }
    }
    """
    try:
        if request.method == 'POST':
            data = request.data
            status_value = data.get('status', '').strip().lower()
            
            if not status_value:
                return Response({
                    'success': False,
                    'message': 'Status is required',
                }, status=status.HTTP_400_BAD_REQUEST)
            
            result = updateAmbulanceAvailabilityService(status_value, request.user)
            
            return Response({
                'success': True,
                'data': result,
            }, status=status.HTTP_200_OK)
        
        else:  # GET
            result = getAmbulanceAvailabilityService(request.user)
            
            return Response({
                'success': True,
                'data': result,
            }, status=status.HTTP_200_OK)
    
    except PHCStaffAmbulancePermissionError as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_403_FORBIDDEN)
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

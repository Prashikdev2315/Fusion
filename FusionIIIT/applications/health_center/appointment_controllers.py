from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated

from .appointment_services import (
    PHCAppointmentError,
    PHCAppointmentPermissionError,
    createAmbulanceRequestService,
    createAppointmentService,
    createVisitService,
    getAmbulanceRequestsService,
    getDoctorScheduleService,
    getStaffAppointmentsService,
    getUserAppointmentsService,
    getVisitHistoryService,
    updateAmbulanceRequestStatusService,
    updateStaffAppointmentStatusService,
)
from .controller_serializers import (
    AmbulanceRequestCreateSerializer,
    AmbulanceStatusUpdateSerializer,
    AppointmentBookSerializer,
    DoctorAvailabilityQuerySerializer,
    StaffAppointmentStatusSerializer,
    VisitCreateSerializer,
)
from .controller_utils import error_response, get_raw_request, success_response
from .migrations.services import resolve_authenticated_user


def _resolve_request_user(request):
    return resolve_authenticated_user(get_raw_request(request))


def _auth_guard(request):
    request_user = _resolve_request_user(request)
    if not request_user:
        return None, error_response('Authentication required', status.HTTP_401_UNAUTHORIZED)
    return request_user, None


def _validate(serializer_cls, data):
    serializer = serializer_cls(data=data)
    if serializer.is_valid():
        return serializer.validated_data, None
    return None, error_response('Validation failed', status.HTTP_400_BAD_REQUEST, errors=serializer.errors)


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def bookAppointmentController(request):
    request_user, auth_error = _auth_guard(request)
    if auth_error:
        return auth_error

    payload, validation_error = _validate(AppointmentBookSerializer, request.data)
    if validation_error:
        return validation_error

    try:
        data = createAppointmentService(payload, request_user)
        return success_response(data=data, status_code=status.HTTP_201_CREATED)
    except PHCAppointmentPermissionError as exc:
        return error_response(exc, status.HTTP_403_FORBIDDEN)
    except PHCAppointmentError as exc:
        return error_response(exc, status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def getAppointmentsController(request):
    request_user, auth_error = _auth_guard(request)
    if auth_error:
        return auth_error

    try:
        data = getUserAppointmentsService(request_user)
        return success_response(data=data)
    except PHCAppointmentPermissionError as exc:
        return error_response(exc, status.HTTP_403_FORBIDDEN)
    except PHCAppointmentError as exc:
        return error_response(exc, status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def getDoctorAvailabilityController(request):
    request_user, auth_error = _auth_guard(request)
    if auth_error:
        return auth_error

    params, validation_error = _validate(DoctorAvailabilityQuerySerializer, request.query_params)
    if validation_error:
        return validation_error

    try:
        data = getDoctorScheduleService(
            doctor_id=params.get('doctor_id'),
            date_value=params.get('date'),
        )
        return success_response(data=data)
    except PHCAppointmentPermissionError as exc:
        return error_response(exc, status.HTTP_403_FORBIDDEN)
    except PHCAppointmentError as exc:
        return error_response(exc, status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def getStaffAppointmentsController(request):
    request_user, auth_error = _auth_guard(request)
    if auth_error:
        return auth_error

    try:
        if request.method == 'GET':
            data = getStaffAppointmentsService(request_user)
            return success_response(data=data)

        payload, validation_error = _validate(StaffAppointmentStatusSerializer, request.data)
        if validation_error:
            return validation_error

        data = updateStaffAppointmentStatusService(
            appointment_id=payload.get('appointment_id'),
            status=payload.get('status'),
            notes=payload.get('notes', ''),
            request_user=request_user,
        )
        return success_response(data=data)
    except PHCAppointmentPermissionError as exc:
        return error_response(exc, status.HTTP_403_FORBIDDEN)
    except PHCAppointmentError as exc:
        return error_response(exc, status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def updateStaffAppointmentStatusController(request):
    request_user, auth_error = _auth_guard(request)
    if auth_error:
        return auth_error

    payload, validation_error = _validate(StaffAppointmentStatusSerializer, request.data)
    if validation_error:
        return validation_error

    try:
        data = updateStaffAppointmentStatusService(
            appointment_id=payload.get('appointment_id'),
            status=payload.get('status'),
            notes=payload.get('notes', ''),
            request_user=request_user,
        )
        return success_response(data=data)
    except PHCAppointmentPermissionError as exc:
        return error_response(exc, status.HTTP_403_FORBIDDEN)
    except PHCAppointmentError as exc:
        return error_response(exc, status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def createVisitController(request):
    request_user, auth_error = _auth_guard(request)
    if auth_error:
        return auth_error

    payload, validation_error = _validate(VisitCreateSerializer, request.data)
    if validation_error:
        return validation_error

    try:
        data = createVisitService(payload, request_user)
        return success_response(data=data, status_code=status.HTTP_201_CREATED)
    except PHCAppointmentPermissionError as exc:
        return error_response(exc, status.HTTP_403_FORBIDDEN)
    except PHCAppointmentError as exc:
        return error_response(exc, status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def getVisitHistoryController(request):
    request_user, auth_error = _auth_guard(request)
    if auth_error:
        return auth_error

    try:
        data = getVisitHistoryService(request_user)
        return success_response(data=data)
    except PHCAppointmentPermissionError as exc:
        return error_response(exc, status.HTTP_403_FORBIDDEN)
    except PHCAppointmentError as exc:
        return error_response(exc, status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def ambulanceRequestsController(request):
    """Compatibility endpoint for frontend: /phc/api/ambulance/."""
    request_user, auth_error = _auth_guard(request)
    if auth_error:
        return auth_error

    try:
        if request.method == 'GET':
            status_filter = request.query_params.get('status')
            data = getAmbulanceRequestsService(request_user, status=status_filter)
            return success_response(data=data)

        payload, validation_error = _validate(AmbulanceRequestCreateSerializer, request.data)
        if validation_error:
            return validation_error

        data = createAmbulanceRequestService(payload, request_user)
        return success_response(data=data, status_code=status.HTTP_201_CREATED)
    except PHCAppointmentPermissionError as exc:
        return error_response(exc, status.HTTP_403_FORBIDDEN)
    except PHCAppointmentError as exc:
        return error_response(exc, status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def updateAmbulanceRequestStatusController(request):
    request_user, auth_error = _auth_guard(request)
    if auth_error:
        return auth_error

    payload, validation_error = _validate(AmbulanceStatusUpdateSerializer, request.data)
    if validation_error:
        return validation_error

    try:
        data = updateAmbulanceRequestStatusService(
            request_id=payload.get('request_id'),
            new_status=payload.get('status'),
            notes=payload.get('notes', ''),
            request_user=request_user,
        )
        return success_response(data=data)
    except PHCAppointmentPermissionError as exc:
        return error_response(exc, status.HTTP_403_FORBIDDEN)
    except PHCAppointmentError as exc:
        return error_response(exc, status.HTTP_400_BAD_REQUEST)

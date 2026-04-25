from django.core.exceptions import PermissionDenied
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated

from .controller_serializers import ReimbursementRequestSerializer
from .controller_utils import error_response, get_raw_request, success_response
from .migrations.services import resolve_authenticated_user
from .patient_feature_services import (
    PHCPatientFeatureError,
    applyReimbursementService,
    downloadMedicalRecordsService,
    getDoctorsService,
    getMedicalRecordsService,
    getReimbursementStatusService,
)


def _resolve_request_user(request):
    return resolve_authenticated_user(get_raw_request(request))


def _auth_guard(request):
    user = _resolve_request_user(request)
    if not user:
        return None, error_response('Authentication required', status.HTTP_401_UNAUTHORIZED)
    return user, None


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def getDoctorsController(request):
    request_user, auth_error = _auth_guard(request)
    if auth_error:
        return auth_error

    try:
        data = getDoctorsService(request_user)
        return success_response(data=data)
    except PermissionDenied as exc:
        return error_response(exc, status.HTTP_403_FORBIDDEN)


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def getMedicalRecordsController(request):
    request_user, auth_error = _auth_guard(request)
    if auth_error:
        return auth_error

    try:
        data = getMedicalRecordsService(request_user)
        return success_response(data=data)
    except PermissionDenied as exc:
        return error_response(exc, status.HTTP_403_FORBIDDEN)


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def downloadMedicalRecordsController(request):
    request_user, auth_error = _auth_guard(request)
    if auth_error:
        return auth_error

    try:
        return downloadMedicalRecordsService(request_user)
    except PermissionDenied as exc:
        return error_response(exc, status.HTTP_403_FORBIDDEN)


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def applyReimbursementController(request):
    request_user, auth_error = _auth_guard(request)
    if auth_error:
        return auth_error

    try:
        is_multipart = 'multipart/form-data' in (request.content_type or '').lower()
        if is_multipart:
            payload = request.data.dict()
            documents = request.FILES.getlist('documents')
        else:
            serializer = ReimbursementRequestSerializer(data=request.data)
            if not serializer.is_valid():
                return error_response('Validation failed', status.HTTP_400_BAD_REQUEST, errors=serializer.errors)
            payload = serializer.validated_data
            documents = []

        data = applyReimbursementService(payload, request_user, documents=documents, request=get_raw_request(request))
        return success_response(data=data, status_code=status.HTTP_201_CREATED)
    except PermissionDenied as exc:
        return error_response(exc, status.HTTP_403_FORBIDDEN)
    except PHCPatientFeatureError as exc:
        return error_response(exc, status.HTTP_400_BAD_REQUEST)
    except Exception as exc:
        return error_response(f'Server error: {str(exc)}', status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def getReimbursementStatusController(request):
    request_user, auth_error = _auth_guard(request)
    if auth_error:
        return auth_error

    try:
        data = getReimbursementStatusService(request_user, request=get_raw_request(request))
        return success_response(data=data)
    except PermissionDenied as exc:
        return error_response(exc, status.HTTP_403_FORBIDDEN)

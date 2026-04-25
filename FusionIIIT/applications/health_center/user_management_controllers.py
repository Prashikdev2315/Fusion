from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated

from .controller_serializers import CreateUserRequestSerializer, RoleFilterQuerySerializer
from .controller_utils import error_response, get_raw_request, success_response
from .migrations.services import resolve_authenticated_user
from .user_management_services import (
    PHCUserManagementError,
    PHCUserManagementPermissionError,
    createUserService,
    getUsersByRoleService,
)


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
def createUserController(request):
    request_user, auth_error = _auth_guard(request)
    if auth_error:
        return auth_error

    payload, validation_error = _validate(CreateUserRequestSerializer, request.data)
    if validation_error:
        return validation_error

    try:
        created_user = createUserService(payload, request_user)
        return success_response(
            message='User created successfully',
            data=created_user,
            status_code=status.HTTP_201_CREATED,
        )
    except PHCUserManagementPermissionError as exc:
        return error_response(exc, status.HTTP_403_FORBIDDEN)
    except PHCUserManagementError as exc:
        return error_response(exc, status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def getUsersController(request):
    request_user, auth_error = _auth_guard(request)
    if auth_error:
        return auth_error

    params, validation_error = _validate(RoleFilterQuerySerializer, request.query_params)
    if validation_error:
        return validation_error

    try:
        users = getUsersByRoleService(params.get('role'), request_user)
        return success_response(data=users, count=len(users))
    except PHCUserManagementPermissionError as exc:
        return error_response(exc, status.HTTP_403_FORBIDDEN)
    except PHCUserManagementError as exc:
        return error_response(exc, status.HTTP_400_BAD_REQUEST)

"""
Shared utility helpers for PHC controller layer.

Provides:
  - success_response  — standard 200/201 JSON wrapper
  - error_response    — standard error JSON wrapper
  - get_raw_request   — unwrap DRF request to plain Django HttpRequest
"""

from rest_framework import status as drf_status
from rest_framework.response import Response


def success_response(data=None, message=None, count=None, status_code=drf_status.HTTP_200_OK):
    """Return a standardised success Response."""
    payload = {'success': True}
    if message is not None:
        payload['message'] = message
    if data is not None:
        payload['data'] = data
    if count is not None:
        payload['count'] = count
    return Response(payload, status=status_code)


def error_response(message, status_code=drf_status.HTTP_400_BAD_REQUEST, errors=None):
    """Return a standardised error Response."""
    payload = {
        'success': False,
        'message': str(message),
    }
    if errors is not None:
        payload['errors'] = errors
    return Response(payload, status=status_code)


def get_raw_request(drf_request):
    """Return the underlying Django HttpRequest from a DRF Request object."""
    # DRF wraps the original request; _request holds the raw Django object.
    return getattr(drf_request, '_request', drf_request)

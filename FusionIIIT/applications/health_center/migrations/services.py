"""PHC service helpers for request-level processing.

Business/process helpers live here by project convention.
"""

from django.db import migrations
from .selectors import select_user_by_token_key


class Migration(migrations.Migration):
    dependencies = []
    operations = []


def resolve_authenticated_user(request):
    """Resolve authenticated user from session auth or DRF token header."""
    if getattr(request, 'user', None) and request.user.is_authenticated:
        return request.user

    auth_header = request.META.get('HTTP_AUTHORIZATION', '')
    parts = auth_header.split()
    if len(parts) == 2 and parts[0].lower() == 'token':
        return select_user_by_token_key(parts[1])

    return None

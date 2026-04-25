"""PHC selectors module.

Query-only helpers live here by project convention.
"""

from django.db import migrations
from rest_framework.authtoken.models import Token


class Migration(migrations.Migration):
    dependencies = []
    operations = []


def select_user_by_token_key(token_key):
    """Return token user for a valid auth token key, else None."""
    if not token_key:
        return None

    token = Token.objects.filter(key=token_key).select_related('user').first()
    return token.user if token else None

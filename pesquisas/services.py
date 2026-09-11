import hashlib
import hmac

from django.conf import settings

from .models import somente_digitos


def gerar_hash_documento(documento):
    """Gera um identificador determinístico sem persistir o CPF ou CNPJ em claro."""
    return hmac.new(
        settings.SECRET_SALT.encode('utf-8'),
        somente_digitos(documento).encode('ascii'),
        hashlib.sha256,
    ).hexdigest()
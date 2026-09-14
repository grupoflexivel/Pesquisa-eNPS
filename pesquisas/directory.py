import re
import ssl
import uuid
from dataclasses import dataclass
from enum import Enum
from urllib.parse import urlparse

from django.conf import settings


class DirectoryResult(str, Enum):
    OK = 'ok'
    INVALID = 'invalid'
    DISABLED = 'disabled'
    EXPIRED = 'expired'
    LOCKED = 'locked'
    PASSWORD_EXPIRED = 'password_expired'
    MUST_CHANGE_PASSWORD = 'must_change_password'
    NOT_FOUND = 'not_found'
    AMBIGUOUS = 'ambiguous'
    UNAVAILABLE = 'unavailable'


@dataclass(frozen=True)
class DirectoryEntry:
    dn: str
    guid: uuid.UUID


_SUBCODES = {
    '525': DirectoryResult.NOT_FOUND,
    '52e': DirectoryResult.INVALID,
    '530': DirectoryResult.DISABLED,
    '531': DirectoryResult.DISABLED,
    '532': DirectoryResult.PASSWORD_EXPIRED,
    '533': DirectoryResult.DISABLED,
    '701': DirectoryResult.EXPIRED,
    '773': DirectoryResult.MUST_CHANGE_PASSWORD,
    '775': DirectoryResult.LOCKED,
}


def guid_from_raw(value):
    """Converte objectGUID do AD (bytes little-endian) para UUID."""
    if isinstance(value, str):
        value = value.encode('latin-1')
    if not isinstance(value, bytes) or len(value) != 16:
        raise ValueError('objectGUID invalido')
    return uuid.UUID(bytes_le=value)


def _subcode(message):
    match = re.search(r'data\s+([0-9a-fA-F]+)', message or '')
    return match.group(1).lower() if match else None


class DirectoryClient:
    """Cliente minimo de autenticacao AD, sem sincronizacao de atributos."""

    def __init__(self):
        if not settings.LDAP_SERVER:
            raise RuntimeError('A integracao LDAP esta desabilitada.')

        from ldap3 import NONE, Server, Tls

        server_value = settings.LDAP_SERVER
        if not server_value.startswith(('ldap://', 'ldaps://')):
            server_value = f'ldap://{server_value}'

        parsed = urlparse(server_value)
        if parsed.scheme.lower() not in {'ldap', 'ldaps'} or not parsed.hostname:
            raise RuntimeError('LDAP_SERVER deve ser uma URI ou host LDAP válido.')
        
        is_ldaps = parsed.scheme.lower() == 'ldaps'
        self._start_tls = is_ldaps  # Desativa StartTLS na porta 389 padrão para evitar falhas de socket

        server_options = {
            'port': parsed.port or (636 if is_ldaps else 389),
            'use_ssl': is_ldaps,
            'get_info': NONE,
            'connect_timeout': 5,
            'tls': Tls(validate=ssl.CERT_NONE),
        }
        self._server = Server(parsed.hostname, **server_options)
        self._base_dn = settings.LDAP_BASE_DN
        self._bind_user = self._service_bind_user(settings.LDAP_BIND_USER)
        self._bind_password = settings.LDAP_BIND_PASSWORD
        self._receive_timeout = 10

    @staticmethod
    def _service_bind_user(bind_user):
        if '@' in bind_user or '\\' in bind_user or '=' in bind_user:
            return bind_user
        return f'{bind_user}@{settings.LDAP_DOMAIN}'

    def _connection(self, user, password):
        from ldap3 import AUTO_BIND_NONE, Connection

        return Connection(
            self._server,
            user=user,
            password=password,
            auto_bind=AUTO_BIND_NONE,
            receive_timeout=self._receive_timeout,
            read_only=True,
            raise_exceptions=False,
        )

    def _filter_for(self, login):
        from ldap3.utils.conv import escape_filter_chars

        escaped = escape_filter_chars(login)
        return f'(&(objectCategory=person)(objectClass=user)(sAMAccountName={escaped}))'

    def _open_secure_connection(self, connection):
        try:
            connection.open()
            if self._start_tls and not connection.start_tls():
                return False
            return True
        except Exception:
            return False

    def find_user(self, login):
        from ldap3 import SUBTREE
        from ldap3.core.exceptions import LDAPException

        connection = None
        try:
            connection = self._connection(self._bind_user, self._bind_password)
            if not self._open_secure_connection(connection):
                return DirectoryResult.UNAVAILABLE
            if not connection.bind():
                return DirectoryResult.UNAVAILABLE
            connection.search(
                self._base_dn,
                self._filter_for(login),
                SUBTREE,
                attributes=['objectGUID'],
                size_limit=2,
            )
            entries = [
                item for item in connection.response
                if item.get('type') == 'searchResEntry'
            ]
        except LDAPException:
            return DirectoryResult.UNAVAILABLE
        finally:
            if connection is not None:
                try:
                    if getattr(connection, 'closed', False) is False:
                        connection.unbind()
                except Exception:
                    pass

        if not entries:
            return DirectoryResult.NOT_FOUND
        if len(entries) > 1:
            return DirectoryResult.AMBIGUOUS

        raw_attributes = entries[0].get('raw_attributes', {})
        values = raw_attributes.get('objectGUID') or raw_attributes.get('objectguid') or []
        if not values:
            return DirectoryResult.NOT_FOUND
        try:
            return DirectoryEntry(entries[0]['dn'], guid_from_raw(values[0]))
        except (KeyError, TypeError, ValueError):
            return DirectoryResult.UNAVAILABLE

    def verify_credentials(self, dn, password):
        if not password:
            return DirectoryResult.INVALID

        from ldap3.core.exceptions import LDAPException

        connection = None
        try:
            connection = self._connection(dn, password)
            if not self._open_secure_connection(connection):
                return DirectoryResult.UNAVAILABLE
            if connection.bind():
                return DirectoryResult.OK
            result = connection.result or {}
            code = _subcode(result.get('message', ''))
            return _SUBCODES.get(code, DirectoryResult.INVALID)
        except LDAPException:
            return DirectoryResult.UNAVAILABLE
        finally:
            if connection is not None:
                try:
                    if getattr(connection, 'closed', False) is False:
                        connection.unbind()
                except Exception:
                    pass
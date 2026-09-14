import logging
from dataclasses import dataclass
from datetime import timedelta
from functools import lru_cache

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import BaseBackend
from django.db import transaction
from django.utils import timezone

from .directory import DirectoryClient, DirectoryResult


logger = logging.getLogger('pesquisas.auth')
MAX_LOCAL_ATTEMPTS = 5
LOCAL_LOCK_DURATION = timedelta(minutes=1)


class AuthenticationOutcome:
    OK = 'ok'
    INVALID = 'invalid'
    DISABLED = 'disabled'
    EXPIRED = 'expired'
    LOCKED = 'locked'
    PASSWORD_EXPIRED = 'password_expired'
    MUST_CHANGE_PASSWORD = 'must_change_password'
    DIRECTORY_UNAVAILABLE = 'directory_unavailable'
    IDENTITY_MISMATCH = 'identity_mismatch'


@dataclass(frozen=True)
class AuthenticationResult:
    outcome: str
    user: object = None


def normalize_login(login):
    return (login or '').strip().lower()


@lru_cache(maxsize=1)
def get_directory_client():
    return DirectoryClient()


def _client_ip(request):
    return request.META.get('REMOTE_ADDR', '-') if request is not None else '-'


def _audit(outcome, login, request=None, source=None):
    level = logging.INFO
    if outcome in {
        AuthenticationOutcome.DISABLED,
        AuthenticationOutcome.EXPIRED,
        AuthenticationOutcome.LOCKED,
        AuthenticationOutcome.PASSWORD_EXPIRED,
        AuthenticationOutcome.MUST_CHANGE_PASSWORD,
    }:
        level = logging.WARNING
    elif outcome in {
        AuthenticationOutcome.DIRECTORY_UNAVAILABLE,
        AuthenticationOutcome.IDENTITY_MISMATCH,
    }:
        level = logging.ERROR
    logger.log(level, 'login outcome=%s login=%s source=%s ip=%s', outcome, login, source or '-', _client_ip(request))


class AuthenticationService:
    def authenticate(self, login, password, request=None):
        login = normalize_login(login)
        if not login or not password:
            return AuthenticationResult(AuthenticationOutcome.INVALID)

        User = get_user_model()
        # __iexact mantém compatibilidade com cadastros antigos; novos saves
        # já persistem o login normalizado em minúsculas.
        user = User.objects.filter(username__iexact=login).first()
        if user is None or not user.is_active:
            _audit(AuthenticationOutcome.INVALID, login, request)
            return AuthenticationResult(AuthenticationOutcome.INVALID)

        if user.auth_source == User.AuthSource.LOCAL:
            return self._authenticate_local(user, password, request)
        return self._authenticate_directory(user, password, request)

    def _authenticate_local(self, user, password, request):
        now = timezone.now()
        if user.locked_until and user.locked_until > now:
            _audit(AuthenticationOutcome.INVALID, user.username, request, 'LOCAL')
            return AuthenticationResult(AuthenticationOutcome.INVALID)

        if user.check_password(password):
            if user.failed_login_attempts or user.locked_until:
                user.failed_login_attempts = 0
                user.locked_until = None
                user.save(update_fields=['failed_login_attempts', 'locked_until'])
            _audit(AuthenticationOutcome.OK, user.username, request, 'LOCAL')
            return AuthenticationResult(AuthenticationOutcome.OK, user)

        user.failed_login_attempts += 1
        if user.failed_login_attempts >= MAX_LOCAL_ATTEMPTS:
            user.locked_until = now + LOCAL_LOCK_DURATION
        user.save(update_fields=['failed_login_attempts', 'locked_until'])
        _audit(AuthenticationOutcome.INVALID, user.username, request, 'LOCAL')
        return AuthenticationResult(AuthenticationOutcome.INVALID)

    def _authenticate_directory(self, user, password, request):
        login = user.username
        try:
            entry = get_directory_client().find_user(login)
        except Exception:
            logger.exception('falha ao consultar diretorio login=%s', login)
            entry = DirectoryResult.UNAVAILABLE

        if entry == DirectoryResult.UNAVAILABLE:
            _audit(AuthenticationOutcome.DIRECTORY_UNAVAILABLE, login, request, 'DIRECTORY')
            return AuthenticationResult(AuthenticationOutcome.DIRECTORY_UNAVAILABLE)
        if entry in {DirectoryResult.NOT_FOUND, DirectoryResult.AMBIGUOUS}:
            _audit(AuthenticationOutcome.INVALID, login, request, 'DIRECTORY')
            return AuthenticationResult(AuthenticationOutcome.INVALID)

        if user.directory_guid is not None and user.directory_guid != entry.guid:
            _audit(AuthenticationOutcome.IDENTITY_MISMATCH, login, request, 'DIRECTORY')
            return AuthenticationResult(AuthenticationOutcome.IDENTITY_MISMATCH)

        try:
            outcome = get_directory_client().verify_credentials(entry.dn, password)
        except Exception:
            logger.exception('falha ao validar credencial no diretorio login=%s', login)
            outcome = DirectoryResult.UNAVAILABLE

        if outcome == DirectoryResult.UNAVAILABLE:
            _audit(AuthenticationOutcome.DIRECTORY_UNAVAILABLE, login, request, 'DIRECTORY')
            return AuthenticationResult(AuthenticationOutcome.DIRECTORY_UNAVAILABLE)
        if outcome != DirectoryResult.OK:
            mapped = {
                DirectoryResult.DISABLED: AuthenticationOutcome.DISABLED,
                DirectoryResult.EXPIRED: AuthenticationOutcome.EXPIRED,
                DirectoryResult.LOCKED: AuthenticationOutcome.LOCKED,
                DirectoryResult.PASSWORD_EXPIRED: AuthenticationOutcome.PASSWORD_EXPIRED,
                DirectoryResult.MUST_CHANGE_PASSWORD: AuthenticationOutcome.MUST_CHANGE_PASSWORD,
            }.get(outcome, AuthenticationOutcome.INVALID)
            _audit(mapped, login, request, 'DIRECTORY')
            return AuthenticationResult(mapped)

        if user.directory_guid is None:
            with transaction.atomic():
                locked_user = type(user).objects.select_for_update().get(pk=user.pk)
                if locked_user.directory_guid is None:
                    locked_user.directory_guid = entry.guid
                    locked_user.save(update_fields=['directory_guid'])
                    logger.info('objectGUID vinculado login=%s source=DIRECTORY', login)
                elif locked_user.directory_guid != entry.guid:
                    _audit(AuthenticationOutcome.IDENTITY_MISMATCH, login, request, 'DIRECTORY')
                    return AuthenticationResult(AuthenticationOutcome.IDENTITY_MISMATCH)
                user = locked_user

        _audit(AuthenticationOutcome.OK, login, request, 'DIRECTORY')
        return AuthenticationResult(AuthenticationOutcome.OK, user)


class HybridAuthenticationBackend(BaseBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        result = AuthenticationService().authenticate(username, password, request)
        if request is not None:
            request.auth_outcome = result.outcome
        if result.outcome == AuthenticationOutcome.OK:
            return result.user
        return None

    def get_user(self, user_id):
        User = get_user_model()
        try:
            return User.objects.get(pk=user_id, is_active=True)
        except User.DoesNotExist:
            return None

"""OTP challenges and revocable sessions stored in Redis."""
import json
import hmac
import logging
import time
import uuid
from dataclasses import dataclass
from functools import wraps
from psycopg.errors import UniqueViolation
from redis.exceptions import LockError
from module.entities.user import User
from module.redis_db import get_redis
from module.repo.user_repo import UserRepo
from module.services.helper_service import HelperService
from module.schemas import SignupRequest, ChangeDetailsRequest, normalize_email

OTP_EXPIRY = 600
TOKEN_EXPIRY = 900
RESET_TOKEN_EXPIRY = 300
SESSION_EXPIRY = 30 * 24 * 60 * 60

@dataclass
class Response:
    status: int
    message: str
    data: dict | None = None

class AuthError(Exception):
    def __init__(self, status, message):
        self.status = status
        super().__init__(message)

def service_result(method):
    @wraps(method)
    def wrapped(*args, **kwargs):
        try:
            return method(*args, **kwargs)
        except AuthError as error:
            return Response(error.status, str(error))
        except UniqueViolation:
            return Response(409, 'Username or email already used')
        except (ValueError, TypeError):
            return Response(400, 'Invalid request')
        except LockError:
            return Response(429, 'Operation in progress; retry shortly')
        except Exception:
            logging.getLogger(__name__).exception('Authentication operation failed')
            return Response(503, 'Authentication service unavailable')
    return wrapped

def public_user(user):
    return {field: getattr(user, field) for field in
            ('username', 'name', 'email', 'is_editor')} | {'user_id': str(user.user_id)}

class AuthService:
    @staticmethod
    def _rate(identity, action, maximum=5):
        redis = get_redis()
        key = f'rate:{action}:{HelperService.fingerprint(identity.lower())}'
        # One atomic operation: fixed window expires even if the worker dies.
        count = redis.eval("local n=redis.call('INCR',KEYS[1]); "
                           "if n==1 then redis.call('EXPIRE',KEYS[1],900) end; return n", 1, key)
        if count > maximum:
            raise AuthError(429, 'Too many requests; retry after 15 minutes')

    @staticmethod
    def _unique(username=None, email=None, user_id=None):
        for field, value in (('username', username), ('email', email)):
            if value is not None:
                user = UserRepo.get_user(value=value, search_by=field)
                if user and str(user.user_id) != str(user_id):
                    raise AuthError(409, f'{field.capitalize()} already used')

    @staticmethod
    def _issue(kind, data):
        challenge_id = str(uuid.uuid4())
        otp = HelperService.generate_otp()
        data = dict(data, otp_hash=HelperService.fingerprint(otp),
                    otp_expiry=int(time.time()) + OTP_EXPIRY,
                    sent_at=int(time.time()), attempts=0)
        key = f'{kind}:{challenge_id}'
        redis = get_redis()
        redis.set(key, json.dumps(data), ex=TOKEN_EXPIRY)
        try:
            HelperService.send_otp(data['email'], otp)
        except Exception:
            redis.delete(key)
            raise
        token = HelperService.create_token({'token_type': kind, 'challenge_id': challenge_id}, TOKEN_EXPIRY)
        return Response(200, 'Verification code sent', {
            'token': token, 'token_type': kind, 'expires_in': TOKEN_EXPIRY,
            'otp_expires_in': OTP_EXPIRY, 'resend_after': 60,
        })

    @staticmethod
    def _challenge(token, kind):
        payload = HelperService.verify_token(token)
        if not payload or payload.get('token_type') != kind or not payload.get('challenge_id'):
            raise AuthError(401, 'Invalid or expired token')
        return f'{kind}:{payload["challenge_id"]}'

    @staticmethod
    def _load(key):
        raw = get_redis().get(key)
        if not raw:
            raise AuthError(401, 'Invalid or expired token')
        return json.loads(raw)

    @staticmethod
    def _check_otp(key, data, otp):
        if data['otp_expiry'] <= int(time.time()):
            raise AuthError(400, 'Verification code expired; request a new code')
        if not hmac.compare_digest(data['otp_hash'], HelperService.fingerprint(otp)):
            data['attempts'] += 1
            if data['attempts'] >= 5:
                get_redis().delete(key)
                raise AuthError(429, 'Too many incorrect codes; start again')
            get_redis().set(key, json.dumps(data), keepttl=True)
            raise AuthError(400, 'Invalid verification code')

    @staticmethod
    def session_user(session):
        payload = HelperService.verify_token(session)
        if not payload or payload.get('token_type') != 'session' or not payload.get('session_id'):
            raise AuthError(401, 'Invalid or expired session')
        key = f'session:{payload["session_id"]}'
        cached = AuthService._load(key)
        user = UserRepo.get_user(value=cached['user_id'], search_by='user_id')
        if not user or cached.get('password_version') != HelperService.fingerprint(user.password_hash):
            get_redis().delete(key)
            raise AuthError(401, 'Session revoked; sign in again')
        return user, key

    @staticmethod
    def _session(user):
        session_id = str(uuid.uuid4())
        get_redis().set(f'session:{session_id}', json.dumps({
            'user_id': str(user.user_id),
            'password_version': HelperService.fingerprint(user.password_hash),
        }), ex=SESSION_EXPIRY)
        token = HelperService.create_token({'session_id': session_id, 'token_type': 'session'}, SESSION_EXPIRY)
        return Response(200, 'Signed in successfully', {
            'token': token, 'token_type': 'Bearer', 'expires_in': SESSION_EXPIRY,
            'user': public_user(user),
        })

    @staticmethod
    @service_result
    def init_signup(username, name, email, password):
        request = SignupRequest(username=username, name=name, email=email, password=password)
        AuthService._rate(request.email, 'signup')
        AuthService._unique(username=request.username, email=request.email)
        return AuthService._issue('signup', dict(
            user_id=str(uuid.uuid4()), username=request.username, name=request.name,
            email=request.email, password_hash=HelperService.hash(request.password), is_editor=False,
        ))

    @staticmethod
    @service_result
    def init_signin(id, password):
        identity = id.strip().lower()
        AuthService._rate(identity, 'signin', 10)
        user = UserRepo.get_user(value=identity, search_by='username') or UserRepo.get_user(value=identity, search_by='email')
        if not user or not HelperService.verify(password, user.password_hash):
            raise AuthError(401, 'Invalid username/email or password')
        return AuthService._issue('signin', {
            'email': user.email, 'user_id': str(user.user_id),
            'password_version': HelperService.fingerprint(user.password_hash),
        })

    @staticmethod
    @service_result
    def init_forgot_password(email):
        email = normalize_email(email)
        AuthService._rate(email, 'forgot-password')
        user = UserRepo.get_user(value=email, search_by='email')
        if not user:
            raise AuthError(404, 'User not registered')
        return AuthService._issue('forgot_pass', {
            'email': user.email, 'user_id': str(user.user_id),
            'password_version': HelperService.fingerprint(user.password_hash),
        })

    @staticmethod
    @service_result
    def init_change_details(session, field, value):
        request = ChangeDetailsRequest(field=field, value=value)
        user, _ = AuthService.session_user(session)
        AuthService._rate(str(user.user_id), 'change-details')
        AuthService._unique(**{field: request.value}, user_id=user.user_id) if field in ('email', 'username') else None
        return AuthService._issue('change_details', {
            'user_id': str(user.user_id), 'field': field,
            'value': HelperService.hash(request.value) if field == 'password' else request.value,
            # Verify the new address when changing email; otherwise the current address.
            'email': request.value if field == 'email' else user.email,
            'password_version': HelperService.fingerprint(user.password_hash),
        })

    @staticmethod
    @service_result
    def _resend(token, kind, session=None):
        key = AuthService._challenge(token, kind)
        redis = get_redis()
        with redis.lock(f'lock:{key}', timeout=30, blocking_timeout=2):
            data = AuthService._load(key)
            if kind == 'change_details':
                user, _ = AuthService.session_user(session)
                if str(user.user_id) != data['user_id']:
                    raise AuthError(403, 'Challenge belongs to another user')
            if int(time.time()) - data['sent_at'] < 60:
                raise AuthError(429, 'Wait 60 seconds before resending')
            AuthService._rate(data['email'], 'resend')
            result = AuthService._issue(kind, data)
            redis.delete(key)
            return result

    @staticmethod
    @service_result
    def _verify(token, otp, kind, session=None):
        key = AuthService._challenge(token, kind)
        redis = get_redis()
        with redis.lock(f'lock:{key}', timeout=30, blocking_timeout=2):
            data = AuthService._load(key)
            if kind == 'change_details':
                user, _ = AuthService.session_user(session)
                if str(user.user_id) != data['user_id']:
                    raise AuthError(403, 'Challenge belongs to another user')
            AuthService._check_otp(key, data, otp)
            if kind == 'signup':
                AuthService._unique(username=data['username'], email=data['email'])
                user = User(**{field: data[field] for field in
                              ('user_id', 'username', 'name', 'email', 'password_hash', 'is_editor')})
                UserRepo.create(user_data=user)
                result = Response(201, 'Account created; sign in to continue', {'user': public_user(user)})
            else:
                user = UserRepo.get_user(value=data['user_id'], search_by='user_id')
                if not user or data['password_version'] != HelperService.fingerprint(user.password_hash):
                    raise AuthError(401, 'Account changed; start again')
                if kind == 'signin':
                    result = AuthService._session(user)
                elif kind == 'forgot_pass':
                    reset_id = str(uuid.uuid4())
                    redis.set(f'reset:{reset_id}', json.dumps({
                        'user_id': data['user_id'], 'password_version': data['password_version'],
                    }), ex=RESET_TOKEN_EXPIRY)
                    result = Response(200, 'Code verified', {
                        'token': HelperService.create_token({'token_type': 'reset', 'challenge_id': reset_id}, RESET_TOKEN_EXPIRY),
                        'token_type': 'reset', 'expires_in': RESET_TOKEN_EXPIRY,
                    })
                else:
                    field, value = data['field'], data['value']
                    if field in ('username', 'email'):
                        AuthService._unique(**{field: value}, user_id=user.user_id)
                    UserRepo.update_user(user.user_id, 'password_hash' if field == 'password' else field, value)
                    result = Response(200, f'{field.capitalize()} updated', {'sign_in_required': field == 'password'})
            redis.delete(key)
            return result

    resend_signup_otp = staticmethod(lambda token: AuthService._resend(token, 'signup'))
    resend_signin_otp = staticmethod(lambda token: AuthService._resend(token, 'signin'))
    resend_forgot_pass_otp = staticmethod(lambda token: AuthService._resend(token, 'forgot_pass'))
    resend_change_details = staticmethod(lambda session, token: AuthService._resend(token, 'change_details', session))
    verify_signup_otp = staticmethod(lambda token, otp: AuthService._verify(token, otp, 'signup'))
    verify_signin_otp = staticmethod(lambda token, otp: AuthService._verify(token, otp, 'signin'))
    verify_forgot_pass_otp = staticmethod(lambda token, otp: AuthService._verify(token, otp, 'forgot_pass'))
    verify_change_details = staticmethod(lambda session, token, otp: AuthService._verify(token, otp, 'change_details', session))

    @staticmethod
    @service_result
    def set_new_password(token, password):
        if not 8 <= len(password) <= 128:
            raise AuthError(400, 'Password must be 8–128 characters')
        key = AuthService._challenge(token, 'reset')
        redis = get_redis()
        with redis.lock(f'lock:{key}', timeout=30, blocking_timeout=2):
            data = AuthService._load(key)
            user = UserRepo.get_user(value=data['user_id'], search_by='user_id')
            if not user or data['password_version'] != HelperService.fingerprint(user.password_hash):
                raise AuthError(401, 'Account changed; start again')
            UserRepo.update_user(user.user_id, 'password_hash', HelperService.hash(password))
            redis.delete(key)
            return Response(200, 'Password updated; all existing sessions revoked')

    @staticmethod
    @service_result
    def signout(session):
        _, key = AuthService.session_user(session)
        get_redis().delete(key)
        return Response(200, 'Signed out successfully')

    @staticmethod
    @service_result
    def me(session):
        user, _ = AuthService.session_user(session)
        return Response(200, 'Profile retrieved', public_user(user))

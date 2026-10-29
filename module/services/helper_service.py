# module/services/helper_service.py

import jwt
import hashlib
import hmac
import os
import secrets
import time
import smtplib
import ssl
import logging
import json
from email.message import EmailMessage
from email.utils import formataddr
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from typing import Any

class HelperService:
  # ============================================================
  # JWT
  # ============================================================

  @staticmethod
  def get_jwt_secret() -> str:
    secret = os.getenv("JWT_SECRET", "")
    if len(secret) < 32:
      raise RuntimeError("JWT_SECRET must contain at least 32 characters")
    return secret

  @staticmethod
  def create_token(payload: dict[str, Any], expiry_seconds: int) -> str:
    token_payload = {
      **payload,
      "exp": int(time.time()) + expiry_seconds,
    }

    return jwt.encode(
      payload=token_payload,
      key=HelperService.get_jwt_secret(),
      algorithm="HS256",
    )

  @staticmethod
  def verify_token(token: str) -> dict | None:
    try:
      return jwt.decode(
        jwt=token,
        key=HelperService.get_jwt_secret(),
        algorithms=["HS256"],
        options={"require": ["exp", "token_type"]},
      )

    except Exception:
      return None

  # ============================================================
  # OTP
  # ============================================================

  @staticmethod
  def generate_otp() -> str:
    return str(object=(secrets.randbelow(900000) + 100000))

  @staticmethod
  def email_settings() -> dict | None:
    """Validate configuration without connecting or sending email."""
    mode = os.getenv('EMAIL_MODE', 'brevo_smtp').strip().lower()
    if mode == 'console':
      return None
    if mode in ('brevo_smtp', 'brevo_api'):
      sender = os.getenv('BREVO_SENDER_EMAIL', '').strip()
      name = os.getenv('BREVO_SENDER_NAME', 'NewsLens').strip() or 'NewsLens'
      if not sender:
        raise RuntimeError('BREVO_SENDER_EMAIL must be a verified Brevo sender')
      if mode == 'brevo_api':
        api_key = os.getenv('BREVO_API_KEY', '').strip()
        if not api_key:
          raise RuntimeError('BREVO_API_KEY is required for Brevo HTTPS delivery')
        return dict(transport='brevo_api', sender=sender, sender_name=name, api_key=api_key)
      username = os.getenv('BREVO_SMTP_LOGIN', '').strip()
      password = os.getenv('BREVO_SMTP_KEY', '').strip()
      if not username or not password:
        raise RuntimeError('BREVO_SMTP_LOGIN and BREVO_SMTP_KEY are required; use an SMTP key, not an API key')
      port = int(os.getenv('BREVO_SMTP_PORT', '2525'))
      if port not in (2525, 587, 465):
        raise RuntimeError('BREVO_SMTP_PORT must be 2525, 587 or 465')
      return dict(host='smtp-relay.brevo.com', port=port, sender=sender,
                  sender_name=name, username=username, password=password, use_ssl=port == 465)
    if mode == 'gmail':
      address = os.getenv('GMAIL_ADDRESS', '').strip()
      password = ''.join(os.getenv('GMAIL_APP_PASSWORD', '').split())
      if not address or not password:
        raise RuntimeError('GMAIL_ADDRESS and GMAIL_APP_PASSWORD are required for Gmail OTP delivery')
      return dict(host='smtp.gmail.com', port=465, sender=address,
                  username=address, password=password, use_ssl=True)
    if mode != 'smtp':
      raise RuntimeError('EMAIL_MODE must be brevo_smtp, brevo_api, gmail, smtp or console')
    host = os.getenv('SMTP_HOST')
    sender = os.getenv('SMTP_FROM')
    if not host or not sender:
      raise RuntimeError('SMTP_HOST and SMTP_FROM are required')
    username = os.getenv('SMTP_USERNAME')
    password = os.getenv('SMTP_PASSWORD')
    if username and not password:
      raise RuntimeError('SMTP_PASSWORD is required when SMTP_USERNAME is set')
    use_ssl = os.getenv('SMTP_SSL', 'false').lower() == 'true'
    return dict(host=host, sender=sender, username=username, password=password,
                use_ssl=use_ssl, port=int(os.getenv('SMTP_PORT', '465' if use_ssl else '587')))

  @staticmethod
  def send_otp(email: str, otp: str) -> None:
    settings = HelperService.email_settings()
    if settings is None:
      logging.getLogger(__name__).warning('Development OTP for %s: %s', email, otp)
      return
    subject = 'Your Fake News App verification code'
    content = (f'Your verification code is {otp}. It expires in 10 minutes.\n'
               'If you did not request this code, ignore this email.')
    if settings.get('transport') == 'brevo_api':
      HelperService._send_brevo_api(settings, email, subject, content)
      return
    message = EmailMessage()
    message['Subject'] = subject
    message['From'] = (formataddr((settings['sender_name'], settings['sender']))
                       if settings.get('sender_name') else settings['sender'])
    message['To'] = email
    message.set_content(content)
    use_ssl = settings['use_ssl']
    client = smtplib.SMTP_SSL if use_ssl else smtplib.SMTP
    options = {'timeout': 15}
    if use_ssl:
      options['context'] = ssl.create_default_context()
    with client(settings['host'], settings['port'], **options) as smtp:
      if not use_ssl:
        smtp.starttls(context=ssl.create_default_context())
      if settings['username']:
        smtp.login(settings['username'], settings['password'])
      smtp.send_message(message)

  @staticmethod
  def _send_brevo_api(settings: dict, email: str, subject: str, content: str) -> None:
    """HTTPS alternative for hosts that restrict SMTP; never log keys or OTPs."""
    payload = {
      'sender': {'email': settings['sender'], 'name': settings['sender_name']},
      'to': [{'email': email}], 'subject': subject, 'textContent': content,
    }
    request = Request('https://api.brevo.com/v3/smtp/email',
                      data=json.dumps(payload).encode('utf-8'), method='POST',
                      headers={'api-key': settings['api_key'], 'Accept': 'application/json',
                               'Content-Type': 'application/json'})
    try:
      with urlopen(request, timeout=15) as response:
        if response.status != 201:
          raise RuntimeError(f'Brevo email API returned HTTP {response.status}')
    except HTTPError as error:
      # The provider body can contain request data. Surface only a safe hint.
      status = error.code
      error.close()
      hints = {400: 'check the verified sender and email settings',
               401: 'check BREVO_API_KEY', 403: 'check sender verification and account access',
               429: 'email rate limit reached; retry later'}
      hint = hints.get(status, 'email provider unavailable; retry later')
      raise RuntimeError(f'Brevo email API returned HTTP {status}: {hint}') from None
    except (URLError, TimeoutError):
      raise RuntimeError('Cannot reach the Brevo email API; check outbound HTTPS connectivity') from None

  @staticmethod
  def fingerprint(value: str) -> str:
    return hmac.new(HelperService.get_jwt_secret().encode(), value.encode(), hashlib.sha256).hexdigest()

  # ============================================================
  # PASSWORD HASHING
  # ============================================================

  @staticmethod
  def hash(password: str) -> str:
    salt = secrets.token_bytes(nbytes=16)

    password_hash = hashlib.scrypt(
      password=password.encode(encoding="utf-8"),
      salt=salt,
      n=16384,
      r=8,
      p=1,
      dklen=64,
    )

    return (salt.hex() + ":" + password_hash.hex())

  @staticmethod
  def verify(password: str, stored: str) -> bool:
    try:
      salt_hex, stored_hash_hex = stored.split(sep=":")

      salt = bytes.fromhex(salt_hex)
      stored_hash = bytes.fromhex(stored_hash_hex)

      verify_hash = hashlib.scrypt(
        password=password.encode(encoding="utf-8"),
        salt=salt,
        n=16384,
        r=8,
        p=1,
        dklen=64,
      )

      return hmac.compare_digest(stored_hash, verify_hash)

    except Exception:
      return False

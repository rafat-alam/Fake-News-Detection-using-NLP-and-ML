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
from email.message import EmailMessage

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
    mode = os.getenv('EMAIL_MODE', 'gmail').strip().lower()
    if mode == 'console':
      return None
    if mode == 'gmail':
      address = os.getenv('GMAIL_ADDRESS', '').strip()
      password = ''.join(os.getenv('GMAIL_APP_PASSWORD', '').split())
      if not address or not password:
        raise RuntimeError('GMAIL_ADDRESS and GMAIL_APP_PASSWORD are required for Gmail OTP delivery')
      return dict(host='smtp.gmail.com', port=465, sender=address,
                  username=address, password=password, use_ssl=True)
    if mode != 'smtp':
      raise RuntimeError('EMAIL_MODE must be gmail, smtp or console')
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
    message = EmailMessage()
    message['Subject'] = 'Your Fake News App verification code'
    message['From'] = settings['sender']
    message['To'] = email
    message.set_content(f'Your verification code is {otp}. It expires in 10 minutes.\n'
                        'If you did not request this code, ignore this email.')
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

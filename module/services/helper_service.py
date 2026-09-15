# module/services/helper_service.py

import jwt
import hashlib
import hmac
import os
import secrets
import time

from typing import Any

class HelperService:
  # ============================================================
  # JWT
  # ============================================================

  @staticmethod
  def get_jwt_secret() -> str:
    return os.getenv(key="JWT_SECRET")

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
  def send_otp(email: str, otp: str) -> None:
    print("Email:", email)
    print("OTP:", otp)

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

      salt = bytes.fromhex(string=salt_hex)
      stored_hash = bytes.fromhex(string=stored_hash_hex)

      verify_hash = hashlib.scrypt(
        password=password.encode(encoding="utf-8"),
        salt=salt,
        n=16384,
        r=8,
        p=1,
        dklen=64,
      )

      return hmac.compare_digest(a=stored_hash, b=verify_hash)

    except Exception:
      return False

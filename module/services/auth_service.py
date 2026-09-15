# module/services/auth_service.py

import json
import time
import uuid

from dataclasses import dataclass
from module.entities.user import User
from module.redis_db import get_redis
from module.repo.user_repo import UserRepo
from module.services.helper_service import HelperService

EMAIL_ALREADY_USED = "Email already Used!"
EXPIRED_OTP = "OTP Expired!"
FIELD_UPDATED_SUCCESSFULLY = (
  "{Field} updated Successfully!"
)
INTERNAL_SERVER_ERROR = "INTERNAL SERVER ERROR!"
INVALID_FIELD = "Invalid Field!"
INVALID_OTP = "Invalid OTP!"
INVALID_OR_EXPIRED_TOKEN = "Invalid or Expired Token!"
OTP_NOT_VERIFIED = "OTP not Verified!"
OTP_SENT_RECENTLY = (
  "OTP sent recently, try again in {time_remaining} seconds!"
)
PASSWORD_UPDATED = "Password updated Successfully!"
USER_CREATED = "User verified and created Successfully!"
USER_NOT_FOUND = "User not Registered!"
USERNAME_ALREADY_USED = "Username already Used!"
WRONG_PASSWORD = "Wrong Password!"

OTP_EXPIRY = 10 * 60                 # 10 minutes
RESET_TOKEN_EXPIRY = 5 * 60          # 05 minutes
SESSION_EXPIRY = 30 * 24 * 60 * 60   # 30 days
TOKEN_EXPIRY = 15 * 60               # 15 minutes

@dataclass
class Response:
  status: int
  message: str

class AuthService:
  # ============================================================
  # INIT SIGNUP
  # ============================================================

  @staticmethod
  def init_signup(username: str, name: str, email: str, password: str) -> Response:
    try:
      if UserRepo.get_user(value=username, search_by="username"):
        return Response(status=400, message=USERNAME_ALREADY_USED)

      if UserRepo.get_user(value=email, search_by="email"):
        return Response(status=400, message=EMAIL_ALREADY_USED)

      signup_id = str(object=uuid.uuid4())
      user_id = str(object=uuid.uuid4())
      password_hash = HelperService.hash(password=password)
      otp = HelperService.generate_otp()
      otp_expiry = int(time.time()) + OTP_EXPIRY

      redis_payload = {
        "user_id": user_id,
        "username": username,
        "name": name,
        "email": email,
        "password_hash": password_hash,
        "is_editor": False,
        "otp": otp,
        "otp_expiry": otp_expiry,
      }

      payload = {
        "signup_id": signup_id,
        "token_type": "signup",
      }

      redis_client = get_redis()
      redis_client.set(name=f"signup:{signup_id}", value=json.dumps(obj=redis_payload), ex=TOKEN_EXPIRY)
      HelperService.send_otp(email=email, otp=otp)
      token = HelperService.create_token(payload=payload, expiry_seconds=TOKEN_EXPIRY)
      return Response(status=200, message=token)

    except Exception:
      return Response(status=500, message=INTERNAL_SERVER_ERROR)

  # ============================================================
  # RESEND SIGNUP OTP
  # ============================================================

  @staticmethod
  def resend_signup_otp(token: str) -> Response:
    try:
      token = HelperService.verify_token(token=token)

      if not token or token.get("token_type") != "signup":
        return Response(status=400, message=INVALID_OR_EXPIRED_TOKEN)

      redis_client = get_redis()
      redis_data = redis_client.get(name=f"signup:{token.get("signup_id")}")

      if not redis_data:
        return Response(status=400, message=INVALID_OR_EXPIRED_TOKEN)

      redis_data = json.loads(s=redis_data)
      current_time = int(time.time())

      if redis_data["otp_expiry"] > current_time + 540:
        time_remaining = redis_data["otp_expiry"] - (current_time + 540)
        return Response(status=400, message=OTP_SENT_RECENTLY.format(time_remaining=time_remaining))

      signup_id = str(object=uuid.uuid4())
      redis_data["otp"] = HelperService.generate_otp()
      redis_data["otp_expiry"] = (int(time.time()) + OTP_EXPIRY)

      payload = {
        "signup_id": signup_id,
        "token_type": "signup",
      }

      redis_client.delete(f"signup:{token.get("signup_id")}")
      redis_client.set(name=f"signup:{signup_id}", value=json.dumps(obj=redis_data), ex=TOKEN_EXPIRY)
      HelperService.send_otp(email=redis_data["email"], otp=redis_data["otp"])
      token = HelperService.create_token(payload=payload, expiry_seconds=TOKEN_EXPIRY)
      return Response(status=200, message=token)

    except Exception:
      return Response(status=500, message=INTERNAL_SERVER_ERROR)

  # ============================================================
  # VERIFY SIGNUP OTP
  # ============================================================

  @staticmethod
  def verify_signup_otp(token: str, otp: str) -> Response:
    try:
      token = HelperService.verify_token(token=token)

      if not token or token.get("token_type") != "signup":
        return Response(status=400, message=INVALID_OR_EXPIRED_TOKEN)

      redis_client = get_redis()
      redis_data = redis_client.get(name=f"signup:{token.get("signup_id")}")

      if not redis_data:
        return Response(status=400, message=INVALID_OR_EXPIRED_TOKEN)

      redis_data = json.loads(s=redis_data)

      if redis_data["otp"] != otp:
        return Response(status=400, message=INVALID_OTP)

      if redis_data["otp_expiry"] < int(time.time()):
        return Response(status=400, message=EXPIRED_OTP)

      if UserRepo.get_user(value=redis_data["username"], search_by="username"):
        return Response(status=400, message=USERNAME_ALREADY_USED)

      if UserRepo.get_user(value=redis_data["email"], search_by="email"):
        return Response(status=400, message=EMAIL_ALREADY_USED)

      user = User(
        user_id=redis_data["user_id"],
        username=redis_data["username"],
        name=redis_data["name"],
        email=redis_data["email"],
        password_hash=redis_data["password_hash"],
        is_editor=redis_data["is_editor"],
      )

      UserRepo.create(user_data=user)
      redis_client.delete(f"signup:{token.get("signup_id")}")
      return Response(status=200, message=USER_CREATED)

    except Exception:
      return Response(status=500, message=INTERNAL_SERVER_ERROR)

  # ============================================================
  # INIT FORGOT PASSWORD
  # ============================================================

  @staticmethod
  def init_forgot_password(email: str) -> Response:
    try:
      if not UserRepo.get_user(value=email, search_by="email"):
        return Response(status=400, message=USER_NOT_FOUND)

      forgot_pass_id = str(object=uuid.uuid4())
      otp = HelperService.generate_otp()
      otp_expiry = (int(time.time()) + OTP_EXPIRY)

      redis_payload = {
        "email": email,
        "otp": otp,
        "otp_expiry": otp_expiry,
        "can_reset": False,
      }

      payload = {
        "forgot_pass_id": forgot_pass_id,
        "token_type": "forgot_pass",
      }

      redis_client = get_redis()
      redis_client.set(name=f"forgot_pass:{forgot_pass_id}", value=json.dumps(obj=redis_payload), ex=TOKEN_EXPIRY)
      HelperService.send_otp(email=email, otp=otp)
      token = HelperService.create_token(payload=payload, expiry_seconds=TOKEN_EXPIRY)
      return Response(status=200, message=token)

    except Exception:
      return Response(status=500, message=INTERNAL_SERVER_ERROR)

  # ============================================================
  # RESEND FORGOT PASSWORD OTP
  # ============================================================

  @staticmethod
  def resend_forgot_pass_otp(token: str) -> Response:
    try:
      token = HelperService.verify_token(token=token)

      if not token or token.get("token_type") != "forgot_pass":
        return Response(status=400, message=INVALID_OR_EXPIRED_TOKEN)

      redis_client = get_redis()
      redis_data = redis_client.get(name=f"forgot_pass:{token.get("forgot_pass_id")}")

      if not redis_data:
        return Response(status=400, message=INVALID_OR_EXPIRED_TOKEN)

      redis_data = json.loads(s=redis_data)

      if redis_data["can_reset"] != False:
        return Response(status=400, message=INVALID_OR_EXPIRED_TOKEN)

      current_time = int(time.time())

      if redis_data["otp_expiry"] > current_time + 540:
        time_remaining = redis_data["otp_expiry"] - (current_time + 540)
        return Response(status=400, message=OTP_SENT_RECENTLY.format(time_remaining=time_remaining))

      forgot_pass_id = str(object=uuid.uuid4())
      redis_data["otp"] = HelperService.generate_otp()
      redis_data["otp_expiry"] = (int(time.time()) + OTP_EXPIRY)

      payload = {
        "forgot_pass_id": forgot_pass_id,
        "token_type": "forgot_pass",
      }

      redis_client.delete(f"forgot_pass:{token.get("forgot_pass_id")}")
      redis_client.set(name=f"forgot_pass:{forgot_pass_id}", value=json.dumps(obj=redis_data), ex=TOKEN_EXPIRY)
      HelperService.send_otp(email=redis_data["email"], otp=redis_data["otp"])
      new_token = HelperService.create_token(payload=payload, expiry_seconds=TOKEN_EXPIRY)
      return Response(status=200, message=new_token)
    except Exception:
      return Response(status=500, message=INTERNAL_SERVER_ERROR)

  # ============================================================
  # VERIFY FORGOT PASSWORD OTP
  # ============================================================

  @staticmethod
  def verify_forgot_pass_otp(token: str, otp: str) -> Response:
    try:
      token = HelperService.verify_token(token=token)

      if not token or token.get("token_type") != "forgot_pass":
        return Response(status=400, message=INVALID_OR_EXPIRED_TOKEN)

      redis_client = get_redis()
      redis_data = redis_client.get(name=f"forgot_pass:{token.get("forgot_pass_id")}")

      if not redis_data:
        return Response(status=400, message=INVALID_OR_EXPIRED_TOKEN)

      redis_data = json.loads(s=redis_data)

      if redis_data["can_reset"] != False:
        return Response(status=400, message=INVALID_OR_EXPIRED_TOKEN)

      if redis_data["otp"] != otp:
        return Response(status=400, message=INVALID_OTP)

      if redis_data["otp_expiry"] < int(time.time()):
        return Response(status=400, message=EXPIRED_OTP)

      forgot_pass_id = str(object=uuid.uuid4())

      redis_payload = {
        "email": redis_data["email"],
        "can_reset": True,
      }

      payload = {
        "forgot_pass_id": forgot_pass_id,
        "token_type": "forgot_pass",
      }

      redis_client.delete(f"forgot_pass:{token.get("forgot_pass_id")}")
      redis_client.set(name=f"forgot_pass:{forgot_pass_id}", value=json.dumps(obj=redis_payload), ex=RESET_TOKEN_EXPIRY)
      new_token = HelperService.create_token(payload=payload, expiry_seconds=RESET_TOKEN_EXPIRY)
      return Response(status=200, message=new_token)

    except Exception:
      return Response(status=500, message=INTERNAL_SERVER_ERROR)

  # ============================================================
  # SET NEW PASSWORD
  # ============================================================

  @staticmethod
  def set_new_password(token: str, password: str) -> Response:
    try:
      token = HelperService.verify_token(token=token)

      if not token or token.get("token_type") != "forgot_pass":
        return Response(status=400, message=INVALID_OR_EXPIRED_TOKEN)

      redis_client = get_redis()
      redis_data = redis_client.get(name=f"forgot_pass:{token.get("forgot_pass_id")}")

      if not redis_data:
        return Response(status=400, message=INVALID_OR_EXPIRED_TOKEN)

      redis_data = json.loads(s=redis_data)

      if redis_data["can_reset"] != True:
        return Response(status=400, message=OTP_NOT_VERIFIED)

      user = UserRepo.get_user(value=redis_data["email"], search_by="email")

      if not user:
        return Response(status=400, message=USER_NOT_FOUND)

      password_hash = HelperService.hash(password=password)
      UserRepo.update_user(user_id=user.user_id, field="password_hash", value=password_hash)
      redis_client.delete(f"forgot_pass:{token.get("forgot_pass_id")}")
      return Response(status=200, message=PASSWORD_UPDATED)

    except Exception:
      return Response(status=500, message=INTERNAL_SERVER_ERROR)

  # ============================================================
  # INIT SIGNIN
  # ============================================================

  @staticmethod
  def init_signin(id: str, password: str) -> Response:
    try:
      user = (UserRepo.get_user(value=id, search_by="username") or UserRepo.get_user(value=id, search_by="email"))

      if not user:
        return Response(status=400, message=USER_NOT_FOUND)

      if not HelperService.verify(password=password, stored=user.password_hash):
        return Response(status=400, message=WRONG_PASSWORD)

      signin_id = str(object=uuid.uuid4())
      otp = HelperService.generate_otp()
      otp_expiry = (int(time.time()) + OTP_EXPIRY)

      redis_payload = {
        "email": user.email,
        "otp": otp,
        "otp_expiry": otp_expiry,
      }

      payload = {
        "signin_id": signin_id,
        "token_type": "signin",
      }

      redis_client = get_redis()
      redis_client.set(name=f"signin:{signin_id}", value=json.dumps(obj=redis_payload), ex=TOKEN_EXPIRY)
      HelperService.send_otp(email=user.email, otp=otp)
      token = HelperService.create_token(payload=payload, expiry_seconds=TOKEN_EXPIRY)
      return Response(status=200, message=token)

    except Exception:
      return Response(status=500, message=INTERNAL_SERVER_ERROR)

  # ============================================================
  # RESEND SIGNIN OTP
  # ============================================================

  @staticmethod
  def resend_signin_otp(token: str) -> Response:
    try:
      token = HelperService.verify_token(token=token)

      if not token or token.get("token_type") != "signin":
        return Response(status=400, message=INVALID_OR_EXPIRED_TOKEN)

      redis_client = get_redis()
      redis_data = redis_client.get(name=f"signin:{token.get("signin_id")}")

      if not redis_data:
        return Response(status=400, message=INVALID_OR_EXPIRED_TOKEN)

      redis_data = json.loads(s=redis_data)
      current_time = int(time.time())

      if redis_data["otp_expiry"] > current_time + 540:
        time_remaining = redis_data["otp_expiry"] - (current_time + 540)
        return Response(status=400, message=OTP_SENT_RECENTLY.format(time_remaining=time_remaining))

      signin_id = str(object=uuid.uuid4())
      redis_data["otp"] = HelperService.generate_otp()
      redis_data["otp_expiry"] = (int(time.time()) + OTP_EXPIRY)

      payload = {
        "signin_id": signin_id,
        "token_type": "signin",
      }

      redis_client.delete(f"signin:{token.get("signin_id")}")
      redis_client.set(name=f"signin:{signin_id}", value=json.dumps(obj=redis_data), ex=TOKEN_EXPIRY)
      HelperService.send_otp(email=redis_data["email"], otp=redis_data["otp"])
      new_token = HelperService.create_token(payload=payload, expiry_seconds=TOKEN_EXPIRY)
      return Response(status=200, message=new_token)

    except Exception:
      return Response(status=500, message=INTERNAL_SERVER_ERROR)

  # ============================================================
  # VERIFY SIGNIN OTP
  # ============================================================

  @staticmethod
  def verify_signin_otp(token: str, otp: str) -> Response:
    try:
      token = HelperService.verify_token(token=token)

      if not token or token.get("token_type") != "signin":
        return Response(status=400, message=INVALID_OR_EXPIRED_TOKEN)

      redis_client = get_redis()
      redis_data = redis_client.get(name=f"signin:{token.get("signin_id")}")

      if not redis_data:
        return Response(status=400, message=INVALID_OR_EXPIRED_TOKEN)

      redis_data = json.loads(s=redis_data)

      if redis_data["otp"] != otp:
        return Response(status=400, message=INVALID_OTP)

      if redis_data["otp_expiry"] < int(time.time()):
        return Response(status=400, message=EXPIRED_OTP)

      user = UserRepo.get_user(value=redis_data["email"], search_by="email")

      if not user:
        return Response(status=400, message=USER_NOT_FOUND)

      session_id = str(object=uuid.uuid4())

      redis_payload = {
        "user_id": str(object=user.user_id),
        "username": user.username,
        "name": user.name,
        "email": user.email,
        "is_editor": user.is_editor,
      }

      payload = {
        "session_id": session_id,
        "token_type": "session",
      }

      redis_client.delete(f"signin:{token.get("signin_id")}")
      redis_client.set(name=f"session:{session_id}", value=json.dumps(obj=redis_payload), ex=SESSION_EXPIRY)
      token = HelperService.create_token(payload=payload, expiry_seconds=SESSION_EXPIRY)
      return Response(status=200, message=token)

    except Exception:
      return Response(status=500, message=INTERNAL_SERVER_ERROR)

  # ============================================================
  # INIT CHANGE DETAILS
  # ============================================================

  @staticmethod
  def init_change_details(session: str, field: str, value: str) -> Response:
    try:
      allowed_fields = {
        "username",
        "name",
        "email",
        "password"
      }

      if field not in allowed_fields:
        return Response(status=400, message=INVALID_FIELD)

      session = HelperService.verify_token(token=session)

      if not session or session.get("token_type") != "session":
        return Response(status=400, message=INVALID_OR_EXPIRED_TOKEN)

      redis_client = get_redis()
      redis_data = redis_client.get(name=f"session:{session.get("session_id")}")

      if not redis_data:
        return Response(status=400, message=INVALID_OR_EXPIRED_TOKEN)

      redis_data = json.loads(s=redis_data)

      if field == "username" and UserRepo.get_user(value=value, search_by="username"):
        return Response(status=400, message=USERNAME_ALREADY_USED)

      if field == "email" and UserRepo.get_user(value=value, search_by="email"):
        return Response(status=400, message=EMAIL_ALREADY_USED)

      change_details_id = str(object=uuid.uuid4())
      if field == "password":
        value = HelperService.hash(password=value)
      otp = HelperService.generate_otp()
      otp_expiry = int(time.time()) + OTP_EXPIRY

      redis_payload = {
        "user_id": redis_data["user_id"],
        "field": field,
        "value": value,
        "otp": otp,
        "otp_expiry": otp_expiry,
      }

      payload = {
        "change_details_id": change_details_id,
        "token_type": "change_details",
      }

      redis_client.set(name=f"change_details:{change_details_id}", value=json.dumps(obj=redis_payload), ex=TOKEN_EXPIRY)
      HelperService.send_otp(email=redis_data["email"], otp=otp)
      token = HelperService.create_token(payload=payload, expiry_seconds=TOKEN_EXPIRY)
      return Response(status=200, message=token)

    except Exception:
      return Response(status=500, message=INTERNAL_SERVER_ERROR)

  # ============================================================
  # RESEND CHANGE DETAILS OTP
  # ============================================================

  @staticmethod
  def resend_change_details(session: str, token: str) -> Response:
    try:
      session = HelperService.verify_token(token=session)
      
      if not session or session.get("token_type") != "session":
        return Response(status=400, message=INVALID_OR_EXPIRED_TOKEN)

      token = HelperService.verify_token(token=token)

      if not token or token.get("token_type") != "change_details":
        return Response(status=400, message=INVALID_OR_EXPIRED_TOKEN)

      redis_client = get_redis()
      redis_session_data = redis_client.get(name=f"session:{session.get("session_id")}")
      redis_token_data = redis_client.get(name=f"change_details:{token.get("change_details_id")}")

      if not redis_session_data or not redis_token_data:
        return Response(status=400, message=INVALID_OR_EXPIRED_TOKEN)

      redis_session_data = json.loads(s=redis_session_data)
      redis_token_data = json.loads(s=redis_token_data)

      if redis_session_data["user_id"] != redis_token_data["user_id"]:
        return Response(status=400, message=INVALID_OR_EXPIRED_TOKEN)

      current_time = int(time.time())

      if redis_token_data["otp_expiry"] > current_time + 540:
        time_remaining = redis_token_data["otp_expiry"] - (current_time + 540)
        return Response(status=400, message=OTP_SENT_RECENTLY.format(time_remaining=time_remaining))

      change_details_id = str(object=uuid.uuid4())
      redis_token_data["otp"] = HelperService.generate_otp()
      redis_token_data["otp_expiry"] = int(time.time()) + OTP_EXPIRY

      payload = {
        "change_details_id": change_details_id,
        "token_type": "change_details",
      }

      redis_client.delete(f"change_details:{token.get("change_details_id")}")
      redis_client.set(name=f"change_details:{change_details_id}", value=json.dumps(obj=redis_token_data), ex=TOKEN_EXPIRY)
      HelperService.send_otp(email=redis_session_data["email"], otp=redis_token_data["otp"])
      token = HelperService.create_token(payload=payload, expiry_seconds=TOKEN_EXPIRY)
      return Response(status=200, message=token)

    except Exception:
      return Response(status=500, message=INTERNAL_SERVER_ERROR)

  # ============================================================
  # VERIFY CHANGE DETAILS
  # ============================================================

  @staticmethod
  def verify_change_details(session: str, token: str, otp: str) -> Response:
    try:
      session = HelperService.verify_token(token=session)

      if not session or session.get("token_type") != "session":
        return Response(status=400, message=INVALID_OR_EXPIRED_TOKEN)

      token = HelperService.verify_token(token=token)

      if not token or token.get("token_type") != "change_details":
        return Response(status=400, message=INVALID_OR_EXPIRED_TOKEN)

      redis_client = get_redis()
      redis_session_data = redis_client.get(name=f"session:{session.get("session_id")}")
      redis_token_data = redis_client.get(name=f"change_details:{token.get("change_details_id")}")

      if not redis_session_data or not redis_token_data:
        return Response(status=400, message=INVALID_OR_EXPIRED_TOKEN)

      redis_session_data = json.loads(s=redis_session_data)
      redis_token_data = json.loads(s=redis_token_data)

      if redis_session_data["user_id"] != redis_token_data["user_id"]:
        return Response(status=400, message=INVALID_OR_EXPIRED_TOKEN)

      if redis_token_data["otp"] != otp:
        return Response(status=400, message=INVALID_OTP)

      if redis_token_data["otp_expiry"] < int(time.time()):
        return Response(status=400, message=EXPIRED_OTP)

      if redis_token_data["field"] == "username" and UserRepo.get_user(value=redis_token_data["value"], search_by="username"):
        return Response(status=400, message=USERNAME_ALREADY_USED)

      if redis_token_data["field"] == "email" and UserRepo.get_user(value=redis_token_data["value"], search_by="email"):
        return Response(status=400, message=EMAIL_ALREADY_USED)

      if redis_token_data["field"] == "password":
        UserRepo.update_user(user_id=redis_token_data["user_id"], field="password_hash", value=redis_token_data["value"])
      else:
        UserRepo.update_user(user_id=redis_token_data["user_id"], field=redis_token_data["field"], value=redis_token_data["value"])
        redis_session_data[redis_token_data["field"]] = redis_token_data["value"]

      redis_client.delete(f"change_details:{token.get("change_details_id")}")
      redis_client.set(name=f"session:{session.get("session_id")}", value=json.dumps(obj=redis_session_data), keepttl=True)
      return Response(status=200, message=FIELD_UPDATED_SUCCESSFULLY.format(Field=redis_token_data["field"].capitalize()))

    except Exception:
      return Response(status=500, message=INTERNAL_SERVER_ERROR)

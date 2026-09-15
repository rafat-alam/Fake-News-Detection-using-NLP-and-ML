# module/entities/user.py

from dataclasses import dataclass

@dataclass
class User:
  user_id: str
  username: str
  name: str
  email: str
  password_hash: str
  is_editor: bool = False

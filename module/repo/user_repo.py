# module/repo/user_repo.py

from module.database import get_connection
from module.entities.user import User

class UserRepo:
  @staticmethod
  def create(user_data: User) -> None:
    query = """
      INSERT INTO users (user_id, username, name, email, password_hash, is_editor)
      VALUES (%s, %s, %s, %s, %s, %s)
    """

    with get_connection() as connection:
      with connection.cursor() as cursor:
        cursor.execute(query=query, params=(
            user_data.user_id,
            user_data.username,
            user_data.name,
            user_data.email,
            user_data.password_hash,
            user_data.is_editor,
          ),
        )
      connection.commit()

  @staticmethod
  def update_user(user_id: str, field: str, value: str) -> None:
    allowed_fields = {
      "username",
      "name",
      "email",
      "password_hash"
    }

    if field not in allowed_fields:
      return None

    query = f"""
      UPDATE users
      SET {field} = %s
      WHERE user_id = %s
    """

    with get_connection() as connection:
      with connection.cursor() as cursor:
        cursor.execute(query=query, params=(value, user_id,))
      connection.commit()

  @staticmethod
  def get_user(value: str, search_by: str = "username") -> User | None:
    allowed_fields = {
      "username",
      "email",
      "user_id",
    }

    if search_by not in allowed_fields:
      return None

    query = f"""
      SELECT user_id, username, name, email, password_hash, is_editor
      FROM users
      WHERE {search_by} = %s
    """

    with get_connection() as connection:
      with connection.cursor() as cursor:
        cursor.execute(query=query, params=(value,))
        row = cursor.fetchone()

    if not row:
      return None

    return User(
      user_id=row[0],
      username=row[1],
      name=row[2],
      email=row[3],
      password_hash=row[4],
      is_editor=row[5],
    )

  @staticmethod
  def get_all_users() -> list[User]:
    query = """
      SELECT user_id, username, name, email, password_hash, is_editor
      FROM users
    """

    with get_connection() as connection:
      with connection.cursor() as cursor:
        cursor.execute(query=query)
        rows = cursor.fetchall()

    return [
      User(
        user_id=row[0],
        username=row[1],
        name=row[2],
        email=row[3],
        password_hash=row[4],
        is_editor=row[5],
      )
      for row in rows
    ]

# module/create_tables.py

from module.database import get_connection

def create_tables():
  with get_connection() as connection:
    with connection.cursor() as cursor:

      cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
          user_id UUID PRIMARY KEY,
          username VARCHAR(100) UNIQUE NOT NULL,
          name VARCHAR(150) NOT NULL,
          email VARCHAR(255) UNIQUE NOT NULL,
          password_hash VARCHAR(255) NOT NULL,
          is_editor BOOLEAN NOT NULL DEFAULT FALSE
        );
      """)

      cursor.execute("""
        CREATE TABLE IF NOT EXISTS news (
          news_id UUID PRIMARY KEY,
          title VARCHAR(500) NOT NULL,
          text TEXT NOT NULL,
          subject VARCHAR(100) NOT NULL,
          date DATE NOT NULL,
          time TIME NOT NULL,
          published_by UUID NOT NULL,

          CONSTRAINT fk_published_by
            FOREIGN KEY (published_by)
            REFERENCES users(user_id)
            ON DELETE CASCADE
        );
      """)

    connection.commit()

  print("Tables created successfully!")

if __name__ == "__main__":
  create_tables()

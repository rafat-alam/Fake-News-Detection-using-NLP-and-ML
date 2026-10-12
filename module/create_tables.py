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
          published_at TIMESTAMPTZ NOT NULL,
          published_by UUID NOT NULL,
          confidence DOUBLE PRECISION CHECK (confidence BETWEEN 0 AND 1),
          label SMALLINT NOT NULL CHECK (label IN (0, 1)),
          model_key VARCHAR(50) NOT NULL DEFAULT 'logistic_regression'
            CHECK (model_key IN ('logistic_regression', 'passive_aggressive',
                                'naive_bayes', 'decision_tree', 'random_forest')),

          CONSTRAINT fk_published_by
            FOREIGN KEY (published_by)
            REFERENCES users(user_id)
            ON DELETE CASCADE
        );
      """)

      cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS users_username_lower ON users (lower(username))")
      cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS users_email_lower ON users (lower(email))")
      cursor.execute("CREATE INDEX IF NOT EXISTS news_feed ON news (published_at DESC, news_id DESC)")
      cursor.execute("CREATE INDEX IF NOT EXISTS news_author ON news (published_by, published_at DESC)")
      cursor.execute("CREATE INDEX IF NOT EXISTS news_subject ON news (subject)")

    connection.commit()

  print("Tables created successfully!")

if __name__ == "__main__":
  create_tables()

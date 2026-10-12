# module/repo/news_repo.py

from datetime import timezone

from module.database import get_connection
from module.entities.news import News


class NewsRepo:
  COLUMNS = "news_id, title, text, subject, published_at, published_by, confidence, label, model_key"

  @staticmethod
  def _from_row(row) -> News:
    return News(
      news_id=str(row[0]),
      title=row[1],
      text=row[2],
      subject=row[3],
      published_at=row[4].astimezone(timezone.utc),
      published_by=str(row[5]),
      confidence=row[6],
      label=row[7],
      model_key=row[8] if len(row) > 8 else "logistic_regression",
    )

  @staticmethod
  def create(news_data: News) -> None:
    if news_data.published_at.tzinfo is None:
      raise ValueError("published_at must include a timezone")
    published_at = news_data.published_at.astimezone(timezone.utc)
    with get_connection() as connection:
      with connection.cursor() as cursor:
        cursor.execute(
          query=f"INSERT INTO news ({NewsRepo.COLUMNS}) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
          params=(news_data.news_id, news_data.title, news_data.text,
                  news_data.subject, published_at,
                  news_data.published_by, news_data.confidence, news_data.label, news_data.model_key),
        )
      connection.commit()

  @staticmethod
  def get_news(news_id: str) -> News | None:
    with get_connection() as connection:
      with connection.cursor() as cursor:
        cursor.execute(
          query=f"SELECT {NewsRepo.COLUMNS} FROM news WHERE news_id = %s",
          params=(news_id,),
        )
        row = cursor.fetchone()
    return NewsRepo._from_row(row) if row else None

  @staticmethod
  def get_all_news(limit: int = 20, offset: int = 0,
                   published_by: str | None = None, subject=None, label=None, q=None) -> list[News]:
    if not 1 <= limit <= 100 or offset < 0:
      raise ValueError("limit must be between 1 and 100; offset must be non-negative")
    query = f"SELECT {NewsRepo.COLUMNS} FROM news"
    where, params = NewsRepo._filters(published_by, subject, label, q)
    query += where
    query += " ORDER BY published_at DESC, news_id DESC LIMIT %s OFFSET %s"
    params.extend((limit, offset))
    with get_connection() as connection:
      with connection.cursor() as cursor:
        cursor.execute(query=query, params=tuple(params))
        rows = cursor.fetchall()
    return [NewsRepo._from_row(row) for row in rows]

  @staticmethod
  def _filters(published_by=None, subject=None, label=None, q=None):
    clauses, params = [], []
    for column, value in (("published_by", published_by), ("subject", subject), ("label", label)):
      if value is not None:
        clauses.append(f"{column} = %s")
        params.append(value)
    if q:
      # Escape LIKE wildcards so user input is a literal substring.
      pattern = '%' + q.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'
      clauses.append("(title ILIKE %s OR text ILIKE %s)")
      params.extend((pattern, pattern))
    return (' WHERE ' + ' AND '.join(clauses) if clauses else ''), params

  @staticmethod
  def count(published_by=None, subject=None, label=None, q=None):
    where, params = NewsRepo._filters(published_by, subject, label, q)
    with get_connection() as connection:
      with connection.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM news" + where, tuple(params))
        return cursor.fetchone()[0]

  @staticmethod
  def subjects():
    with get_connection() as connection:
      with connection.cursor() as cursor:
        cursor.execute("SELECT DISTINCT subject FROM news ORDER BY subject")
        return [row[0] for row in cursor.fetchall()]

  @staticmethod
  def update_news(news_data: News, published_by: str) -> bool:
    # Match the owner in the write itself, as well as in service authorization.
    with get_connection() as connection:
      with connection.cursor() as cursor:
        cursor.execute(
          query="""
            UPDATE news SET title = %s, text = %s, subject = %s,
                            confidence = %s, label = %s, model_key = %s
            WHERE news_id = %s AND published_by = %s
          """,
          params=(news_data.title, news_data.text, news_data.subject,
                  news_data.confidence, news_data.label, news_data.model_key,
                  news_data.news_id, published_by),
        )
        updated = cursor.rowcount > 0
      connection.commit()
    return updated

  @staticmethod
  def delete_news(news_id: str, published_by: str) -> bool:
    with get_connection() as connection:
      with connection.cursor() as cursor:
        cursor.execute(
          query="DELETE FROM news WHERE news_id = %s AND published_by = %s",
          params=(news_id, published_by),
        )
        deleted = cursor.rowcount > 0
      connection.commit()
    return deleted

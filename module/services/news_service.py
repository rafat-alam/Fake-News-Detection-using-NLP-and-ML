# module/services/news_service.py

import logging
import uuid

from dataclasses import dataclass
from datetime import datetime, timezone
from functools import wraps

from module.entities.news import News
from module.repo.news_repo import NewsRepo
from module.services.auth_service import AuthService, AuthError


logger = logging.getLogger(__name__)


@dataclass
class Response:
  status: int
  message: str
  data: News | list[News] | None = None


class NewsServiceError(Exception):
  def __init__(self, status: int, message: str):
    super().__init__(message)
    self.status = status


def service_result(method):
  @wraps(method)
  def wrapped(*args, **kwargs):
    try:
      return method(*args, **kwargs)
    except NewsServiceError as error:
      return Response(error.status, str(error))
    except Exception:
      logger.exception("News operation failed")
      return Response(500, "Internal server error!")
  return wrapped


class NewsService:
  @staticmethod
  def _uuid(value: str) -> str:
    try:
      return str(uuid.UUID(str(value)))
    except (ValueError, TypeError, AttributeError):
      raise NewsServiceError(400, "Invalid ID!") from None

  @staticmethod
  def _editor(session: str):
    try:
      user, _ = AuthService.session_user(session)
    except AuthError as error:
      raise NewsServiceError(error.status, str(error)) from error
    if not user.is_editor:
      raise NewsServiceError(403, "Editor access required!")
    return user

  @staticmethod
  def _validate(title: str, text: str, subject: str) -> tuple[str, str, str]:
    if not all(isinstance(value, str) for value in (title, text, subject)):
      raise NewsServiceError(400, "Title, text and subject must be strings!")
    title, text, subject = title.strip(), text.strip(), subject.strip()
    if not 3 <= len(title) <= 500 or len(text) < 3 or not 1 <= len(subject) <= 100:
      raise NewsServiceError(400, "Title must be 3–500 characters, text at least 3, and subject 1–100!")
    return title, text, subject

  @staticmethod
  def _predict(title: str, text: str, model: str):
    # Reuse the pipeline loaded by the application's startup lifecycle.
    from model import pipeline
    try:
      return pipeline.predict(title=title, text=text, model_key=model)
    except (KeyError, ValueError) as error:
      raise NewsServiceError(400, str(error)) from error

  @staticmethod
  @service_result
  def create_news(session: str, title: str, text: str, subject: str,
                  model: str = "logistic_regression") -> Response:
    user = NewsService._editor(session)
    title, text, subject = NewsService._validate(title, text, subject)
    result = NewsService._predict(title, text, model)
    news = News(
      news_id=str(uuid.uuid4()), title=title, text=text, subject=subject,
      published_at=datetime.now(timezone.utc), published_by=str(user.user_id),
      confidence=result["confidence"], label=result["label"],
      model_key=model,
    )
    NewsRepo.create(news_data=news)
    return Response(201, "News created successfully!", news)

  @staticmethod
  @service_result
  def get_news(news_id: str) -> Response:
    news = NewsRepo.get_news(news_id=NewsService._uuid(news_id))
    if news is None:
      return Response(404, "News not found!")
    return Response(200, "News retrieved successfully!", news)

  @staticmethod
  @service_result
  def get_all_news(limit: int = 20, offset: int = 0,
                   published_by: str | None = None) -> Response:
    if type(limit) is not int or type(offset) is not int or not 1 <= limit <= 100 or offset < 0:
      raise NewsServiceError(400, "limit must be between 1 and 100; offset must be non-negative")
    if published_by is not None:
      published_by = NewsService._uuid(published_by)
    news = NewsRepo.get_all_news(limit=limit, offset=offset, published_by=published_by)
    return Response(200, "News retrieved successfully!", news)

  @staticmethod
  def _owned_news(news_id: str, user_id: str) -> News:
    news = NewsRepo.get_news(news_id=NewsService._uuid(news_id))
    if news is None:
      raise NewsServiceError(404, "News not found!")
    if str(news.published_by) != str(user_id):
      raise NewsServiceError(403, "You can only modify your own news!")
    return news

  @staticmethod
  @service_result
  def update_news(session: str, news_id: str, title: str, text: str,
                  subject: str, model: str = "logistic_regression") -> Response:
    user = NewsService._editor(session)
    news = NewsService._owned_news(news_id, str(user.user_id))
    title, text, subject = NewsService._validate(title, text, subject)
    result = NewsService._predict(title, text, model)
    news.title, news.text, news.subject = title, text, subject
    news.confidence, news.label = result["confidence"], result["label"]
    news.model_key = model
    if not NewsRepo.update_news(news_data=news, published_by=str(user.user_id)):
      return Response(404, "News not found!")
    return Response(200, "News updated successfully!", news)

  @staticmethod
  @service_result
  def delete_news(session: str, news_id: str) -> Response:
    user = NewsService._editor(session)
    news = NewsService._owned_news(news_id, str(user.user_id))
    if not NewsRepo.delete_news(news_id=news.news_id, published_by=str(user.user_id)):
      return Response(404, "News not found!")
    return Response(200, "News deleted successfully!")

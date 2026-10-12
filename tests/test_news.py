import json
import unittest

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from module.entities.news import News
from module.entities.user import User
from module.repo.news_repo import NewsRepo
from module.services.news_service import NewsService
from module.services.helper_service import HelperService
from module.services.auth_service import AuthService


USER_ID = "00000000-0000-0000-0000-000000000001"
NEWS_ID = "00000000-0000-0000-0000-000000000002"


class NewsTests(unittest.TestCase):
  def setUp(self):
    self.user = User(USER_ID, "editor", "Editor", "editor@example.com", "hash", True)
    self.news = News(NEWS_ID, "Title", "Article text", "Politics",
                     datetime(2026, 1, 1, tzinfo=timezone.utc), USER_ID, 0.9, 1)

  def test_expired_session_cannot_publish(self):
    with patch.object(HelperService, "verify_token", return_value=None), \
         patch.object(NewsRepo, "create") as create:
      result = NewsService.create_news("expired", "Title", "Article text", "Politics")
    self.assertEqual(result.status, 401)
    create.assert_not_called()

  def test_editor_role_is_checked_in_database(self):
    self.user.is_editor = False
    redis = MagicMock()
    redis.get.return_value = json.dumps({"user_id": USER_ID, "is_editor": True,
                                        "password_version": "current"})
    with patch.object(HelperService, "verify_token",
               return_value={"token_type": "session", "session_id": "session"}), \
         patch("module.services.auth_service.get_redis", return_value=redis), \
         patch.object(HelperService, "fingerprint", return_value="current"), \
         patch("module.services.auth_service.UserRepo.get_user", return_value=self.user), \
         patch.object(NewsRepo, "create") as create:
      result = NewsService.create_news("session-token", "Title", "Article text", "Politics")
    self.assertEqual(result.status, 403)
    create.assert_not_called()

  def test_creation_saves_prediction_and_utc_timestamp(self):
    with patch.object(NewsService, "_editor", return_value=self.user), \
         patch.object(NewsService, "_predict", return_value={"confidence": None, "label": 0}), \
         patch.object(NewsRepo, "create") as create:
      result = NewsService.create_news("token", " Title ", " Article text ", " Politics ")
    self.assertEqual(result.status, 201)
    self.assertEqual(result.data.label, 0)
    self.assertIsNone(result.data.confidence)
    self.assertEqual(result.data.title, "Title")
    self.assertEqual(result.data.published_at.tzinfo, timezone.utc)
    self.assertEqual(result.data.published_by, USER_ID)
    create.assert_called_once_with(news_data=result.data)

  def test_other_editor_cannot_delete_article(self):
    self.news.published_by = "00000000-0000-0000-0000-000000000003"
    with patch.object(NewsService, "_editor", return_value=self.user), \
         patch.object(NewsRepo, "get_news", return_value=self.news), \
         patch.object(NewsRepo, "delete_news") as delete:
      result = NewsService.delete_news("token", NEWS_ID)
    self.assertEqual(result.status, 403)
    delete.assert_not_called()

  def test_edit_reclassifies_and_preserves_publication_date(self):
    published_at = self.news.published_at
    with patch.object(NewsService, "_editor", return_value=self.user), \
         patch.object(NewsRepo, "get_news", return_value=self.news), \
         patch.object(NewsService, "_predict", return_value={"confidence": 0.8, "label": 0}), \
         patch.object(NewsRepo, "update_news", return_value=True) as update:
      result = NewsService.update_news("token", NEWS_ID, "New title", "New text", "Science")
    self.assertEqual(result.status, 200)
    self.assertEqual(result.data.label, 0)
    self.assertEqual(result.data.published_at, published_at)
    update.assert_called_once_with(news_data=self.news, published_by=USER_ID)

  def test_invalid_ids_and_pagination_do_not_query_database(self):
    with patch.object(NewsRepo, "get_news") as get, \
         patch.object(NewsRepo, "get_all_news") as get_all:
      self.assertEqual(NewsService.get_news("invalid").status, 400)
      self.assertEqual(NewsService.get_all_news(limit=101).status, 400)
      self.assertEqual(NewsService.get_all_news(offset=-1).status, 400)
    get.assert_not_called()
    get_all.assert_not_called()

  def test_timestamp_is_normalized_to_utc_and_confidence_can_be_absent(self):
    news = NewsRepo._from_row((NEWS_ID, "Title", "Text", "Science",
                              datetime(2026, 1, 1, 17, 30,
                                       tzinfo=timezone(timedelta(hours=5, minutes=30))),
                              USER_ID, None, 1))
    self.assertEqual(news.published_at, datetime(2026, 1, 1, 12, tzinfo=timezone.utc))
    self.assertIsNone(news.confidence)
    self.assertEqual(news.label, 1)

  def test_delete_binds_id_and_owner_in_same_query(self):
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.rowcount = 1
    with patch("module.repo.news_repo.get_connection") as connect:
      connect.return_value.__enter__.return_value = connection
      self.assertTrue(NewsRepo.delete_news(NEWS_ID, USER_ID))
    query = cursor.execute.call_args.kwargs
    self.assertIn("news_id = %s AND published_by = %s", query["query"])
    self.assertEqual(query["params"], (NEWS_ID, USER_ID))
    connection.commit.assert_called_once()


if __name__ == "__main__":
  unittest.main()

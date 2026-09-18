# module/entities/news.py

from dataclasses import dataclass
from datetime import datetime

@dataclass
class News:
  news_id: str
  title: str
  text: str
  subject: str
  published_at: datetime
  published_by: str
  confidence: str
  label: int

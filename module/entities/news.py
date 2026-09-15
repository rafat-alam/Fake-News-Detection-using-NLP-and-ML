# module/entities/news.py

from dataclasses import dataclass
from datetime import date, time

@dataclass
class News:
  news_id: str
  title: str
  text: str
  subject: str
  date: date
  time: time
  published_by: str

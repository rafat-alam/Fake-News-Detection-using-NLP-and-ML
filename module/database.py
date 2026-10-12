# module/database.py

import psycopg
import os

from dotenv import load_dotenv

load_dotenv()

def get_connection():
  database_url = os.getenv("DATABASE_URL")
  if not database_url:
    raise RuntimeError("DATABASE_URL is not set")
  return psycopg.connect(database_url, connect_timeout=10)

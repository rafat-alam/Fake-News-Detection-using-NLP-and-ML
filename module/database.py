# module/database.py

import psycopg
import os

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
  raise ValueError("DATABASE_URL is not set")

def get_connection():
  return psycopg.connect(DATABASE_URL)

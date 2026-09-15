# module/redis_db.py

import os
import redis

from dotenv import load_dotenv

load_dotenv()

REDIS_URL = os.getenv(key="REDIS_URL")

redis_client = redis.Redis.from_url(
  url=REDIS_URL,
  decode_responses=True,
)

def get_redis():
  return redis_client

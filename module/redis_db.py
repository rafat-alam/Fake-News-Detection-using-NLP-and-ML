# module/redis_db.py

import os
import redis

from dotenv import load_dotenv

load_dotenv()

redis_client = None

def get_redis():
  global redis_client
  if redis_client is None:
    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
      raise RuntimeError("REDIS_URL is not set")
    redis_client = redis.Redis.from_url(
      redis_url, decode_responses=True, socket_connect_timeout=5, socket_timeout=5,
    )
  return redis_client

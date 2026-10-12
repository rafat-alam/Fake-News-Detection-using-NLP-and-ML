"""Shared validation and public API models."""
from typing import Literal
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, field_validator

ModelKey = Literal['logistic_regression', 'passive_aggressive', 'naive_bayes', 'decision_tree', 'random_forest']

class RequestModel(BaseModel):
    model_config = ConfigDict(extra='forbid')

def normalize_email(value: str) -> str:
    import re
    value = value.strip().lower()
    if len(value) > 150 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', value):
        raise ValueError('A valid email address is required')
    return value

def normalize_username(value: str) -> str:
    import re
    value = value.strip().lower()
    if not re.fullmatch(r'[a-z0-9_]{3,50}', value):
        raise ValueError('Username must be 3–50 letters, numbers or underscores')
    return value

class SignupRequest(RequestModel):
    username: str
    name: str = Field(min_length=2, max_length=100)
    email: str
    password: str = Field(min_length=8, max_length=128)
    _username = field_validator('username')(normalize_username)
    _email = field_validator('email')(normalize_email)

    @field_validator('name')
    @classmethod
    def valid_name(cls, value):
        value = value.strip()
        if len(value) < 2:
            raise ValueError('Name must contain at least two characters')
        return value

class TokenRequest(RequestModel):
    token: str = Field(min_length=1, max_length=2048)

class VerifyOTPRequest(TokenRequest):
    otp: str = Field(pattern=r'^\d{6}$')

class SigninRequest(RequestModel):
    id: str = Field(min_length=1, max_length=150, description='Username or email')
    password: str = Field(min_length=1, max_length=128)

class ForgotPasswordRequest(RequestModel):
    email: str
    _email = field_validator('email')(normalize_email)

class ResetPasswordRequest(TokenRequest):
    password: str = Field(min_length=8, max_length=128)

class ChangeDetailsRequest(RequestModel):
    field: Literal['username', 'name', 'email', 'password']
    value: str = Field(min_length=1, max_length=150)

    @field_validator('value')
    @classmethod
    def valid_value(cls, value, info):
        field = info.data.get('field')
        if field == 'email':
            return normalize_email(value)
        if field == 'username':
            return normalize_username(value)
        if field == 'password' and not 8 <= len(value) <= 128:
            raise ValueError('Password must be 8–128 characters')
        if field == 'name' and not 2 <= len(value.strip()) <= 100:
            raise ValueError('Name must be 2–100 characters')
        return value if field == 'password' else value.strip()

class NewsPredictionRequest(RequestModel):
    title: str = Field(min_length=3, max_length=500)
    text: str = Field(min_length=3, max_length=100000)
    model: ModelKey = 'logistic_regression'

    @field_validator('title', 'text')
    @classmethod
    def valid_content(cls, value):
        value = value.strip()
        if len(value) < 3:
            raise ValueError('Content must contain at least three characters')
        return value

class NewsWriteRequest(NewsPredictionRequest):
    subject: str = Field(min_length=1, max_length=100)

    @field_validator('subject')
    @classmethod
    def valid_subject(cls, value):
        value = value.strip()
        if not value:
            raise ValueError('Subject is required')
        return value

class NewsPredictionResponse(BaseModel):
    prediction: str
    label: int
    confidence: float | None
    model_used: str
    cleaned_text: str

class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    user_id: str
    username: str
    name: str
    email: str
    is_editor: bool

class NewsPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    news_id: str
    title: str
    text: str
    subject: str
    published_at: datetime
    published_by: str
    confidence: float | None
    label: int
    model_key: ModelKey

class MessageResponse(BaseModel):
    status: int
    message: str
    data: dict | list | None = None

class NewsResponse(BaseModel):
    status: int
    message: str
    data: NewsPublic | None

class NewsPage(BaseModel):
    status: int = 200
    message: str = 'News retrieved successfully!'
    data: list[NewsPublic]
    total: int
    limit: int
    offset: int
    has_more: bool

"""HTTP interface for verified accounts and automatically classified news."""
import logging
import os
from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from module.create_tables import create_tables
from module.database import get_connection
from module.redis_db import get_redis
from module.repo.news_repo import NewsRepo
from module.schemas import (
    SignupRequest, TokenRequest, VerifyOTPRequest, SigninRequest,
    ForgotPasswordRequest, ResetPasswordRequest, ChangeDetailsRequest,
    NewsWriteRequest, MessageResponse, NewsResponse, NewsPage,
)
from module.services.auth_service import AuthService
from module.services.helper_service import HelperService
from module.services.news_service import NewsService
from module.services.user_service import UserService

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app):
    HelperService.get_jwt_secret()
    HelperService.email_settings()
    if os.getenv('AUTO_CREATE_TABLES', 'true').lower() == 'true':
        create_tables()
    get_redis().ping()
    from model import pipeline
    pipeline.load_model(os.getenv('MODEL_PATH', 'models/pretrained_model_01.pkl'))
    app.state.pipeline = pipeline
    yield

app = FastAPI(title='Fake News App API', version='2.0.0', lifespan=lifespan,
              description='OTP accounts and editor news publishing with automatic classification.')
origins = [value.strip() for value in os.getenv('CORS_ORIGINS', '').split(',') if value.strip()]
if origins:
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=False,
                       allow_methods=['GET', 'POST', 'PUT', 'DELETE'],
                       allow_headers=['Authorization', 'Content-Type'])

bearer = HTTPBearer(auto_error=False)

def session_token(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
    if credentials is None or credentials.scheme.lower() != 'bearer':
        raise HTTPException(401, 'Bearer token required', headers={'WWW-Authenticate': 'Bearer'})
    return credentials.credentials

def service_response(result, response):
    if result.status >= 400:
        headers = {'WWW-Authenticate': 'Bearer'} if result.status == 401 else None
        raise HTTPException(result.status, result.message, headers=headers)
    response.status_code = result.status
    return {'status': result.status, 'message': result.message, 'data': result.data}

@app.exception_handler(Exception)
async def unexpected_error(request: Request, error: Exception):
    logger.exception('Request failed: %s %s', request.method, request.url.path,
                     exc_info=(type(error), error, error.__traceback__))
    return JSONResponse(status_code=503, content={'detail': 'Service temporarily unavailable'})

@app.get('/', tags=['Service'])
def root():
    return {'status': 'online', 'version': '2.0.0', 'documentation': '/docs', 'news': '/news'}

@app.get('/health', tags=['Service'])
def health():
    return {'status': 'healthy'}

@app.get('/health/ready', tags=['Service'])
def readiness(request: Request):
    try:
        with get_connection() as connection:
            connection.execute('SELECT 1')
        get_redis().ping()
        if not getattr(request.app.state, 'pipeline', None):
            raise RuntimeError('Model unavailable')
        return {'status': 'ready', 'database': 'ok', 'redis': 'ok', 'model': 'ok'}
    except Exception:
        raise HTTPException(503, 'Service dependencies unavailable') from None

@app.get('/metrics', tags=['Service'])
def metrics(request: Request):
    return {'metrics': request.app.state.pipeline.model_metrics}

@app.post('/auth/signup', tags=['Authentication'], response_model=MessageResponse)
def signup(body: SignupRequest, response: Response):
    return service_response(AuthService.init_signup(**body.model_dump()), response)

@app.post('/auth/signup/resend-otp', tags=['Authentication'], response_model=MessageResponse)
def resend_signup(body: TokenRequest, response: Response):
    return service_response(AuthService.resend_signup_otp(body.token), response)

@app.post('/auth/signup/verify-otp', tags=['Authentication'], response_model=MessageResponse, status_code=201)
def verify_signup(body: VerifyOTPRequest, response: Response):
    return service_response(AuthService.verify_signup_otp(**body.model_dump()), response)

@app.post('/auth/signin', tags=['Authentication'], response_model=MessageResponse)
def signin(body: SigninRequest, response: Response):
    return service_response(AuthService.init_signin(**body.model_dump()), response)

@app.post('/auth/signin/resend-otp', tags=['Authentication'], response_model=MessageResponse)
def resend_signin(body: TokenRequest, response: Response):
    return service_response(AuthService.resend_signin_otp(body.token), response)

@app.post('/auth/signin/verify-otp', tags=['Authentication'], response_model=MessageResponse)
def verify_signin(body: VerifyOTPRequest, response: Response):
    return service_response(AuthService.verify_signin_otp(**body.model_dump()), response)

@app.post('/auth/forgot-password', tags=['Authentication'], response_model=MessageResponse)
def forgot_password(body: ForgotPasswordRequest, response: Response):
    return service_response(AuthService.init_forgot_password(body.email), response)

@app.post('/auth/forgot-password/resend-otp', tags=['Authentication'], response_model=MessageResponse)
def resend_reset(body: TokenRequest, response: Response):
    return service_response(AuthService.resend_forgot_pass_otp(body.token), response)

@app.post('/auth/forgot-password/verify-otp', tags=['Authentication'], response_model=MessageResponse)
def verify_reset(body: VerifyOTPRequest, response: Response):
    return service_response(AuthService.verify_forgot_pass_otp(**body.model_dump()), response)

@app.post('/auth/forgot-password/reset', tags=['Authentication'], response_model=MessageResponse)
def reset_password(body: ResetPasswordRequest, response: Response):
    return service_response(AuthService.set_new_password(**body.model_dump()), response)

@app.post('/auth/change-details', tags=['Account'], response_model=MessageResponse)
def change_details(body: ChangeDetailsRequest, response: Response, session: str = Depends(session_token)):
    return service_response(AuthService.init_change_details(session, **body.model_dump()), response)

@app.post('/auth/change-details/resend-otp', tags=['Account'], response_model=MessageResponse)
def resend_change(body: TokenRequest, response: Response, session: str = Depends(session_token)):
    return service_response(AuthService.resend_change_details(session, body.token), response)

@app.post('/auth/change-details/verify-otp', tags=['Account'], response_model=MessageResponse)
def verify_change(body: VerifyOTPRequest, response: Response, session: str = Depends(session_token)):
    return service_response(AuthService.verify_change_details(session, **body.model_dump()), response)

@app.get('/users/me', tags=['Account'], response_model=MessageResponse)
def me(response: Response, session: str = Depends(session_token)):
    return service_response(AuthService.me(session), response)

@app.post('/auth/signout', tags=['Account'], response_model=MessageResponse)
def signout(response: Response, session: str = Depends(session_token)):
    return service_response(AuthService.signout(session), response)

@app.get('/users/{user_id}', tags=['News'], response_model=MessageResponse)
def author(user_id: UUID, response: Response):
    return service_response(UserService.get_author(str(user_id)), response)

@app.get('/news/subjects', tags=['News'], response_model=MessageResponse)
def subjects():
    return {'status': 200, 'message': 'Subjects retrieved', 'data': NewsRepo.subjects()}

@app.get('/news', tags=['News'], response_model=NewsPage)
def news_feed(limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0),
              published_by: UUID | None = None,
              subject: str | None = Query(None, min_length=1, max_length=100),
              label: int | None = Query(None, ge=0, le=1),
              q: str | None = Query(None, min_length=1, max_length=200)):
    filters = dict(published_by=str(published_by) if published_by else None,
                   subject=subject, label=label, q=q)
    rows = NewsRepo.get_all_news(limit=limit, offset=offset, **filters)
    total = NewsRepo.count(**filters)
    return {'data': rows, 'total': total, 'limit': limit, 'offset': offset,
            'has_more': offset + len(rows) < total}

@app.get('/news/{news_id}', tags=['News'], response_model=NewsResponse)
def news_detail(news_id: UUID, response: Response):
    return service_response(NewsService.get_news(str(news_id)), response)

@app.post('/news', tags=['News'], response_model=NewsResponse, status_code=201)
def publish(body: NewsWriteRequest, response: Response, session: str = Depends(session_token)):
    return service_response(NewsService.create_news(session, **body.model_dump()), response)

@app.put('/news/{news_id}', tags=['News'], response_model=NewsResponse)
def edit(news_id: UUID, body: NewsWriteRequest, response: Response, session: str = Depends(session_token)):
    return service_response(NewsService.update_news(session, str(news_id), **body.model_dump()), response)

@app.delete('/news/{news_id}', tags=['News'], response_model=NewsResponse)
def delete(news_id: UUID, response: Response, session: str = Depends(session_token)):
    return service_response(NewsService.delete_news(session, str(news_id)), response)

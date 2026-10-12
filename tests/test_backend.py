"""Integration tests, enabled only with explicitly isolated local test databases.

TEST_DATABASE_URL must end in /fake_news_test; TEST_REDIS_URL must point to a
dedicated local Redis instance. These test stores are cleared between tests.
"""
import os
import json
import time
import unittest
from urllib.parse import urlparse
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor

ENABLED = bool(os.getenv('TEST_DATABASE_URL') and os.getenv('TEST_REDIS_URL'))

@unittest.skipUnless(ENABLED, 'Set isolated TEST_DATABASE_URL and TEST_REDIS_URL')
class BackendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        db = urlparse(os.environ['TEST_DATABASE_URL'])
        cache = urlparse(os.environ['TEST_REDIS_URL'])
        if db.hostname not in ('127.0.0.1', 'localhost') or db.path != '/fake_news_test':
            raise RuntimeError('Refusing to clear a non-test PostgreSQL database')
        if cache.hostname not in ('127.0.0.1', 'localhost'):
            raise RuntimeError('Use a dedicated local test Redis container')
        cls.environment = patch.dict(os.environ, {
            'DATABASE_URL': os.environ['TEST_DATABASE_URL'],
            'REDIS_URL': os.environ['TEST_REDIS_URL'],
            'JWT_SECRET': 'integration-test-secret-only-0123456789abcdef',
            'EMAIL_MODE': 'console', 'AUTO_CREATE_TABLES': 'true',
        })
        cls.environment.start()
        from module import redis_db
        redis_db.redis_client = None
        from fastapi.testclient import TestClient
        from app import app
        cls.context = TestClient(app)
        cls.client = cls.context.__enter__()
        cls.addClassCleanup(cls.context.__exit__, None, None, None)
        cls.addClassCleanup(cls.environment.stop)

    def setUp(self):
        from module.database import get_connection
        from module.redis_db import get_redis
        with get_connection() as connection:
            connection.execute('TRUNCATE users CASCADE')
        get_redis().flushdb()
        self.codes = {}
        self.mail = patch('module.services.helper_service.HelperService.send_otp',
                          side_effect=lambda email, otp: self.codes.update({email: otp}))
        self.mail.start()
        self.addCleanup(self.mail.stop)

    def request(self, method, path, body=None, token=None, expected=200):
        headers = {'Authorization': f'Bearer {token}'} if token else {}
        kwargs = {'headers': headers}
        if body is not None:
            kwargs['json'] = body
        response = self.client.request(method, path, **kwargs)
        self.assertEqual(response.status_code, expected, response.text)
        return response.json()

    def signup(self, username='editor'):
        email = f'{username}@example.com'
        data = self.request('POST', '/auth/signup', {
            'username': username, 'name': 'Test User', 'email': email, 'password': 'Password123!',
        })['data']
        result = self.request('POST', '/auth/signup/verify-otp', {
            'token': data['token'], 'otp': self.codes[email],
        }, expected=201)
        return result['data']['user']

    def signin(self, username='editor', password='Password123!'):
        challenge = self.request('POST', '/auth/signin', {'id': username, 'password': password})['data']
        return self.request('POST', '/auth/signin/verify-otp', {
            'token': challenge['token'], 'otp': self.codes[f'{username}@example.com'],
        })['data']['token']

    def editor(self, username='editor'):
        from module.repo.user_repo import UserRepo
        user = self.signup(username)
        UserRepo.update_user(user['user_id'], 'is_editor', True)
        return user, self.signin(username)

    def publish(self, token, **changes):
        body = dict(title='Senate passes infrastructure legislation',
                    text='The senate passed legislation funding roads bridges and public transportation.',
                    subject='Politics')
        body.update(changes)
        return self.request('POST', '/news', body, token, 201)['data']

    def test_full_account_and_news_lifecycle(self):
        user, token = self.editor()
        profile = self.request('GET', '/users/me', token=token)['data']
        self.assertTrue(profile['is_editor'])
        self.assertNotIn('password_hash', profile)
        news = self.publish(token)
        self.assertIn(news['label'], (0, 1))
        self.assertEqual(news['model_key'], 'logistic_regression')
        self.assertEqual(news['published_by'], user['user_id'])
        self.assertEqual(self.request('GET', f'/news/{news["news_id"]}')['data'], news)
        page = self.request('GET', '/news?limit=1&subject=Politics&q=infrastructure&label=' + str(news['label']))
        self.assertEqual(page['total'], 1)
        self.assertFalse(page['has_more'])
        self.assertEqual(self.request('GET', '/news/subjects')['data'], ['Politics'])
        author = self.request('GET', f'/users/{user["user_id"]}')['data']
        self.assertNotIn('email', author)
        edited = self.request('PUT', f'/news/{news["news_id"]}', {
            'title': 'NASA launches new science mission',
            'text': 'NASA launched a spacecraft carrying scientific instruments to study the atmosphere.',
            'subject': 'Science', 'model': 'passive_aggressive',
        }, token)['data']
        self.assertEqual(edited['published_at'], news['published_at'])
        self.assertIsNone(edited['confidence'])
        self.assertEqual(edited['model_key'], 'passive_aggressive')
        self.request('DELETE', f'/news/{news["news_id"]}', token=token)
        self.request('GET', f'/news/{news["news_id"]}', expected=404)
        self.request('POST', '/auth/signout', token=token)
        self.request('GET', '/users/me', token=token, expected=401)

    def test_permissions_and_revocation_are_checked_live(self):
        from module.repo.user_repo import UserRepo
        user = self.signup()
        token = self.signin()
        body = dict(title='News headline', text='Article describing political legislation', subject='Politics')
        self.request('POST', '/news', body, token, 403)
        self.request('POST', '/news', body, expected=401)
        UserRepo.update_user(user['user_id'], 'is_editor', True)
        news = self.publish(token)
        _, other_token = self.editor('other')
        self.request('DELETE', f'/news/{news["news_id"]}', token=other_token, expected=403)
        self.request('PUT', f'/news/{news["news_id"]}', body, other_token, 403)
        UserRepo.update_user(user['user_id'], 'is_editor', False)
        self.request('DELETE', f'/news/{news["news_id"]}', token=token, expected=403)

    def test_reset_is_one_time_and_revokes_sessions(self):
        self.signup()
        old_session = self.signin()
        challenge = self.request('POST', '/auth/forgot-password', {'email': 'editor@example.com'})['data']['token']
        self.request('POST', '/auth/forgot-password/reset', {'token': challenge, 'password': 'NewPassword123!'}, expected=401)
        reset = self.request('POST', '/auth/forgot-password/verify-otp', {
            'token': challenge, 'otp': self.codes['editor@example.com'],
        })['data']['token']
        self.request('POST', '/auth/forgot-password/reset', {'token': reset, 'password': 'NewPassword123!'})
        self.request('POST', '/auth/forgot-password/reset', {'token': reset, 'password': 'AnotherPassword!'}, expected=401)
        self.request('GET', '/users/me', token=old_session, expected=401)
        self.request('POST', '/auth/signin', {'id': 'editor', 'password': 'Password123!'}, expected=401)
        self.signin(password='NewPassword123!')

    def test_profile_changes_validate_new_address_and_password(self):
        self.signup()
        session = self.signin()
        other_session = self.signin()
        for field, value in [('name', 'Updated User'), ('username', 'updated'),
                             ('email', 'updated@example.com'), ('password', 'ChangedPassword123!')]:
            challenge = self.request('POST', '/auth/change-details', {'field': field, 'value': value}, session)['data']['token']
            email = 'updated@example.com' if field in ('email', 'password') else 'editor@example.com'
            self.request('POST', '/auth/change-details/verify-otp', {'token': challenge, 'otp': self.codes[email]}, session)
        self.request('GET', '/users/me', token=session, expected=401)
        self.request('GET', '/users/me', token=other_session, expected=401)
        challenge = self.request('POST', '/auth/signin', {'id': 'updated@example.com', 'password': 'ChangedPassword123!'})['data']['token']
        data = self.request('POST', '/auth/signin/verify-otp', {'token': challenge, 'otp': self.codes['updated@example.com']})['data']
        self.assertEqual(data['user']['name'], 'Updated User')

    def test_otp_attempt_limit_expiry_and_resend(self):
        from module.redis_db import get_redis
        from module.services.auth_service import AuthService
        signup = dict(username='newuser', name='Test User', email='newuser@example.com', password='Password123!')
        token = self.request('POST', '/auth/signup', signup)['data']['token']
        self.request('POST', '/auth/signup/resend-otp', {'token': token}, expected=429)
        key = AuthService._challenge(token, 'signup')
        stored = json.loads(get_redis().get(key))
        self.assertNotIn('otp', stored)
        stored['sent_at'] -= 61
        get_redis().set(key, json.dumps(stored), keepttl=True)
        replacement = self.request('POST', '/auth/signup/resend-otp', {'token': token})['data']['token']
        self.request('POST', '/auth/signup/verify-otp', {'token': token, 'otp': self.codes['newuser@example.com']}, expected=401)
        for attempt in range(5):
            self.request('POST', '/auth/signup/verify-otp', {'token': replacement, 'otp': '000000'}, expected=429 if attempt == 4 else 400)
        self.request('POST', '/auth/signup/verify-otp', {'token': replacement, 'otp': self.codes['newuser@example.com']}, expected=401)
        token = self.request('POST', '/auth/signup', signup)['data']['token']
        key = AuthService._challenge(token, 'signup')
        stored = json.loads(get_redis().get(key))
        stored['otp_expiry'] = int(time.time()) - 1
        get_redis().set(key, json.dumps(stored), keepttl=True)
        self.request('POST', '/auth/signup/verify-otp', {'token': token, 'otp': self.codes['newuser@example.com']}, expected=400)

    def test_concurrent_verification_consumes_challenge_once(self):
        token = self.request('POST', '/auth/signup', dict(
            username='newuser', name='Test User', email='newuser@example.com', password='Password123!',
        ))['data']['token']
        body = {'token': token, 'otp': self.codes['newuser@example.com']}
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: self.client.post('/auth/signup/verify-otp', json=body).status_code, range(2)))
        self.assertEqual(sorted(results), [201, 401])

    def test_validation_errors_and_failed_classification_do_not_publish(self):
        _, token = self.editor()
        self.request('POST', '/news', dict(title='the', text='and', subject='Politics'), token, 400)
        self.assertEqual(self.request('GET', '/news')['total'], 0)
        self.request('POST', '/news', dict(title='Title', text='Article', subject='Politics', model='unknown'), token, 422)
        self.request('GET', '/news?limit=101', expected=422)
        self.request('GET', '/news/not-a-uuid', expected=422)
        self.request('POST', '/auth/change-details', {'field': 'is_editor', 'value': 'true'}, token, 422)
        self.request('POST', '/auth/change-details', {'field': 'password', 'value': 'short'}, token, 422)
        self.request('POST', '/auth/signup', dict(username='bad', name='User', email='invalid', password='Password123!'), expected=422)
        self.request('POST', '/predict', dict(title='Title', text='Article'), expected=404)

    def test_pagination_author_filter_literal_search_and_no_secrets(self):
        user, token = self.editor()
        self.publish(token)
        self.publish(token, title='Budget update for government spending')
        page = self.request('GET', '/news?limit=1&published_by=' + user['user_id'])
        self.assertEqual(page['total'], 2)
        self.assertTrue(page['has_more'])
        second = self.request('GET', '/news?limit=1&offset=1')
        self.assertNotEqual(second['data'][0]['news_id'], page['data'][0]['news_id'])
        self.assertEqual(self.request('GET', '/news?q=%25')['total'], 0)

    def test_resend_all_challenges_and_cross_user_rejection(self):
        from module.redis_db import get_redis
        from module.services.auth_service import AuthService
        self.signup()
        session = self.signin()
        self.signup('other')
        other = self.signin('other')
        flows = [('/auth/signin', {'id': 'editor', 'password': 'Password123!'}, 'signin', None),
                 ('/auth/forgot-password', {'email': 'editor@example.com'}, 'forgot_pass', None),
                 ('/auth/change-details', {'field': 'name', 'value': 'New Name'}, 'change_details', session)]
        for route, body, kind, auth in flows:
            token = self.request('POST', route, body, auth)['data']['token']
            if auth:
                self.request('POST', route + '/verify-otp', {'token': token, 'otp': self.codes['editor@example.com']}, other, 403)
            self.request('POST', route + '/resend-otp', {'token': token}, auth, 429)
            key = AuthService._challenge(token, kind)
            data = json.loads(get_redis().get(key))
            data['sent_at'] -= 61
            get_redis().set(key, json.dumps(data), keepttl=True)
            replacement = self.request('POST', route + '/resend-otp', {'token': token}, auth)['data']['token']
            self.request('POST', route + '/verify-otp', {'token': replacement, 'otp': self.codes['editor@example.com']}, auth)

    def test_service_routes_and_expired_wrong_type_tokens(self):
        from module.services.helper_service import HelperService
        self.request('GET', '/')
        self.request('GET', '/health')
        self.request('GET', '/health/ready')
        self.assertEqual(len(self.request('GET', '/metrics')['metrics']), 5)
        schema = self.request('GET', '/openapi.json')
        self.assertNotIn('/predict', schema['paths'])
        self.request('GET', '/users/me', token='garbage', expected=401)
        expired = HelperService.create_token({'token_type': 'session', 'session_id': 'none'}, -1)
        self.request('GET', '/users/me', token=expired, expected=401)
        wrong = HelperService.create_token({'token_type': 'signup', 'challenge_id': 'none'}, 600)
        self.request('GET', '/users/me', token=wrong, expected=401)

if __name__ == '__main__':
    unittest.main()

import os
import json
import unittest
from unittest.mock import patch, ANY, call, sentinel
from urllib.error import HTTPError, URLError
from module.services.helper_service import HelperService

class AuthHelperTests(unittest.TestCase):
    BREVO_ENV = {'EMAIL_MODE': 'brevo_smtp', 'BREVO_SENDER_EMAIL': 'news@example.com',
                 'BREVO_SENDER_NAME': 'NewsLens', 'BREVO_SMTP_LOGIN': 'login@smtp-brevo.com',
                 'BREVO_SMTP_KEY': 'test-smtp-key', 'BREVO_SMTP_PORT': '2525'}

    def test_brevo_smtp_uses_starttls_before_authentication(self):
        with patch.dict(os.environ, self.BREVO_ENV, clear=True), \
             patch('module.services.helper_service.ssl.create_default_context', return_value=sentinel.tls_context) as tls, \
             patch('module.services.helper_service.smtplib.SMTP') as client, \
             patch('module.services.helper_service.smtplib.SMTP_SSL') as ssl_client:
            smtp = client.return_value.__enter__.return_value
            HelperService.send_otp('reader@example.com', '123456')
            client.assert_called_once_with('smtp-relay.brevo.com', 2525, timeout=15)
            ssl_client.assert_not_called()
            tls.assert_called_once_with()
            self.assertEqual(smtp.method_calls[:2], [call.starttls(context=sentinel.tls_context),
                             call.login('login@smtp-brevo.com', 'test-smtp-key')])
            message = smtp.send_message.call_args.args[0]
            self.assertEqual(message['From'], 'NewsLens <news@example.com>')
            self.assertEqual(message['To'], 'reader@example.com')
            self.assertIn('123456', message.get_content())

    def test_brevo_port_465_uses_implicit_tls(self):
        with patch.dict(os.environ, self.BREVO_ENV | {'BREVO_SMTP_PORT': '465'}, clear=True), \
             patch('module.services.helper_service.ssl.create_default_context', return_value=sentinel.tls_context), \
             patch('module.services.helper_service.smtplib.SMTP_SSL') as client:
            HelperService.send_otp('reader@example.com', '123456')
            client.assert_called_once_with('smtp-relay.brevo.com', 465, timeout=15, context=sentinel.tls_context)
            client.return_value.__enter__.return_value.starttls.assert_not_called()

    def test_brevo_missing_settings_fail_before_connecting(self):
        for field in ('BREVO_SENDER_EMAIL', 'BREVO_SMTP_LOGIN', 'BREVO_SMTP_KEY'):
            with self.subTest(field=field), \
                 patch.dict(os.environ, self.BREVO_ENV | {field: ''}, clear=True), \
                 patch('module.services.helper_service.smtplib.SMTP') as client:
                with self.assertRaisesRegex(RuntimeError, field):
                    HelperService.send_otp('reader@example.com', '123456')
                client.assert_not_called()

    def test_brevo_smtp_is_default_and_rejects_unsupported_ports(self):
        env = dict(self.BREVO_ENV)
        del env['EMAIL_MODE']
        del env['BREVO_SMTP_PORT']
        with patch.dict(os.environ, env, clear=True):
            self.assertEqual(HelperService.email_settings()['port'], 2525)
        with patch.dict(os.environ, env | {'BREVO_SMTP_PORT': '25'}, clear=True):
            with self.assertRaisesRegex(RuntimeError, 'BREVO_SMTP_PORT'):
                HelperService.email_settings()

    def test_brevo_api_sends_https_request_without_smtp(self):
        with patch.dict(os.environ, self.BREVO_ENV | {'EMAIL_MODE': 'brevo_api',
                                                    'BREVO_API_KEY': 'test-api-key'}, clear=True), \
             patch('module.services.helper_service.urlopen') as send, \
             patch('module.services.helper_service.smtplib.SMTP') as smtp:
            send.return_value.__enter__.return_value.status = 201
            HelperService.send_otp('reader@example.com', '123456')
            request = send.call_args.args[0]
            self.assertEqual(request.full_url, 'https://api.brevo.com/v3/smtp/email')
            self.assertEqual(request.get_method(), 'POST')
            self.assertEqual(request.get_header('Api-key'), 'test-api-key')
            self.assertEqual(send.call_args.kwargs['timeout'], 15)
            payload = json.loads(request.data)
            self.assertEqual(payload['sender'], {'email': 'news@example.com', 'name': 'NewsLens'})
            self.assertEqual(payload['to'], [{'email': 'reader@example.com'}])
            self.assertIn('123456', payload['textContent'])
            smtp.assert_not_called()

    def test_brevo_api_failures_are_not_reported_as_success_or_leaked(self):
        errors = [HTTPError('https://api.brevo.com/v3/smtp/email', 401,
                            'private-provider-message', {}, None), URLError('private-network-message'),
                  TimeoutError('private-timeout-message')]
        for error in errors:
            with self.subTest(error=type(error).__name__), \
                 patch.dict(os.environ, self.BREVO_ENV | {'EMAIL_MODE': 'brevo_api',
                                                        'BREVO_API_KEY': 'test-api-key'}, clear=True), \
                 patch('module.services.helper_service.urlopen', side_effect=error):
                with self.assertRaises(RuntimeError) as caught:
                    HelperService.send_otp('reader@example.com', '123456')
                self.assertNotIn('private-', str(caught.exception))
                self.assertNotIn('test-api-key', str(caught.exception))
                self.assertNotIn('123456', str(caught.exception))

    def test_brevo_api_requires_api_key_not_smtp_key(self):
        with patch.dict(os.environ, self.BREVO_ENV | {'EMAIL_MODE': 'brevo_api'}, clear=True), \
             patch('module.services.helper_service.urlopen') as send:
            with self.assertRaisesRegex(RuntimeError, 'BREVO_API_KEY'):
                HelperService.send_otp('reader@example.com', '123456')
            send.assert_not_called()

    def test_password_hash_round_trip_and_wrong_password(self):
        stored = HelperService.hash('Password123!')
        self.assertTrue(HelperService.verify('Password123!', stored))
        self.assertFalse(HelperService.verify('WrongPassword', stored))
        self.assertFalse(HelperService.verify('Password123!', 'invalid'))
        self.assertNotEqual(stored, HelperService.hash('Password123!'))

    def test_jwt_expiry_and_required_claims(self):
        with patch.dict(os.environ, {'JWT_SECRET': 'test-jwt-secret-at-least-32-characters'}):
            token = HelperService.create_token({'token_type': 'session', 'session_id': 'test'}, 60)
            self.assertEqual(HelperService.verify_token(token)['session_id'], 'test')
            expired = HelperService.create_token({'token_type': 'session'}, -1)
            self.assertIsNone(HelperService.verify_token(expired))
            self.assertIsNone(HelperService.verify_token('garbage'))

    def test_smtp_transport_uses_tls_and_sends_code(self):
        with patch.dict(os.environ, {'EMAIL_MODE': 'smtp', 'SMTP_HOST': 'smtp.example.com',
                                     'SMTP_FROM': 'news@example.com', 'SMTP_USERNAME': 'user',
                                     'SMTP_PASSWORD': 'password', 'SMTP_PORT': '587', 'SMTP_SSL': 'false'}), \
             patch('module.services.helper_service.smtplib.SMTP') as client:
            smtp = client.return_value.__enter__.return_value
            HelperService.send_otp('reader@example.com', '123456')
            smtp.starttls.assert_called_once()
            smtp.login.assert_called_once_with('user', 'password')
            message = smtp.send_message.call_args.args[0]
            self.assertEqual(message['To'], 'reader@example.com')
            self.assertIn('123456', message.get_content())

    def test_weak_jwt_secret_is_rejected(self):
        with patch.dict(os.environ, {'JWT_SECRET': 'short'}):
            with self.assertRaises(RuntimeError):
                HelperService.get_jwt_secret()

    def test_gmail_uses_ssl_and_app_password(self):
        with patch.dict(os.environ, {'EMAIL_MODE': 'gmail', 'GMAIL_ADDRESS': 'sender@gmail.com',
                                     'GMAIL_APP_PASSWORD': 'abcd efgh ijkl mnop'}), \
             patch('module.services.helper_service.smtplib.SMTP_SSL') as client, \
             patch('module.services.helper_service.smtplib.SMTP') as plain_client:
            smtp = client.return_value.__enter__.return_value
            HelperService.send_otp('reader@example.com', '123456')
            client.assert_called_once_with('smtp.gmail.com', 465, timeout=15, context=ANY)
            plain_client.assert_not_called()
            smtp.starttls.assert_not_called()
            smtp.login.assert_called_once_with('sender@gmail.com', 'abcdefghijklmnop')
            message = smtp.send_message.call_args.args[0]
            self.assertEqual(message['From'], 'sender@gmail.com')
            self.assertEqual(message['To'], 'reader@example.com')
            self.assertIn('123456', message.get_content())

    def test_missing_gmail_credentials_fail_before_connecting(self):
        with patch.dict(os.environ, {'EMAIL_MODE': 'gmail', 'GMAIL_ADDRESS': '', 'GMAIL_APP_PASSWORD': ''}), \
             patch('module.services.helper_service.smtplib.SMTP_SSL') as client:
            with self.assertRaisesRegex(RuntimeError, 'GMAIL_ADDRESS and GMAIL_APP_PASSWORD'):
                HelperService.send_otp('reader@example.com', '123456')
            client.assert_not_called()

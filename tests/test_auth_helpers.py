import os
import unittest
from unittest.mock import patch, ANY
from module.services.helper_service import HelperService

class AuthHelperTests(unittest.TestCase):
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

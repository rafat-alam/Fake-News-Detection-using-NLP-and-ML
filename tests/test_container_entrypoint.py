import os
import signal
import subprocess
import unittest
from unittest.mock import MagicMock, patch
from module.container_entrypoint import main, stop_process

class ContainerEntrypointTests(unittest.TestCase):
    def test_stop_terminates_and_waits(self):
        process = MagicMock()
        process.poll.return_value = None
        stop_process(process)
        process.terminate.assert_called_once()
        process.wait.assert_called_once_with(timeout=10)
        process.kill.assert_not_called()

    def test_stuck_child_is_killed_and_reaped(self):
        process = MagicMock()
        process.poll.return_value = None
        process.wait.side_effect = [subprocess.TimeoutExpired('test', 10), 0]
        stop_process(process)
        process.kill.assert_called_once()
        self.assertEqual(process.wait.call_count, 2)

    def test_failed_redis_startup_never_launches_api(self):
        process = MagicMock()
        process.poll.return_value = 1
        with patch('module.container_entrypoint.subprocess.Popen', return_value=process) as launch, \
             patch('module.container_entrypoint.prepare_runtime'), \
             patch('module.container_entrypoint.signal.signal'), \
             patch('redis.Redis') as client, patch.dict(os.environ), \
             self.assertLogs('module.container_entrypoint', level='ERROR'):
            self.assertEqual(main(), 1)
        launch.assert_called_once()
        client.return_value.close.assert_called_once()

    def test_api_exit_stops_redis(self):
        cache, api = MagicMock(), MagicMock()
        cache.poll.return_value = None
        api.poll.return_value = 1
        with patch('module.container_entrypoint.subprocess.Popen', side_effect=[cache, api]), \
             patch('module.container_entrypoint.prepare_runtime'), \
             patch('module.container_entrypoint.signal.signal'), \
             patch('redis.Redis'), patch.dict(os.environ), \
             self.assertLogs('module.container_entrypoint', level='ERROR'):
            self.assertEqual(main(), 1)
        cache.terminate.assert_called_once()
        cache.wait.assert_called_once_with(timeout=10)

    def test_signal_shuts_down_both_processes(self):
        cache, api = MagicMock(), MagicMock()
        cache.poll.return_value = api.poll.return_value = None
        handlers = {}
        def register(signum, handler):
            handlers[signum] = handler
        with patch('module.container_entrypoint.subprocess.Popen', side_effect=[cache, api]), \
             patch('module.container_entrypoint.prepare_runtime'), \
             patch('module.container_entrypoint.signal.signal', side_effect=register), \
             patch('module.container_entrypoint.time.sleep', side_effect=lambda _: handlers[signal.SIGTERM](signal.SIGTERM, None)), \
             patch('redis.Redis'), patch.dict(os.environ, {'REDIS_URL': 'redis://remote:6379/0'}):
            self.assertEqual(main(), 0)
            self.assertEqual(os.environ['REDIS_URL'], 'redis://127.0.0.1:6379/0')
        api.terminate.assert_called_once()
        cache.terminate.assert_called_once()

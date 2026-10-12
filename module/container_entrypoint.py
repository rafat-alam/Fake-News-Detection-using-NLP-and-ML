"""Run local Redis and Uvicorn together, with coordinated startup/shutdown."""
import logging
import os
import signal
import subprocess
import sys
import time
import stat
from pathlib import Path

logger = logging.getLogger(__name__)

def prepare_runtime(data_dir='/data'):
    """An existing Docker volume can belong to a different image's Redis UID."""
    import pwd

    directory = Path(data_dir)
    if directory.is_symlink():
        raise RuntimeError('Redis data directory must not be a symbolic link')
    if os.geteuid() == 0:
        account = pwd.getpwnam('appuser')
        directory.mkdir(parents=True, exist_ok=True)
        # Preserve all persisted data; repair ownership only within this volume.
        for root, directories, files in os.walk(directory, followlinks=False):
            directories[:] = [name for name in directories if not Path(root, name).is_symlink()]
            os.chown(root, account.pw_uid, account.pw_gid)
            os.chmod(root, stat.S_IMODE(os.stat(root).st_mode) | stat.S_IRWXU)
            for name in files:
                path = Path(root, name)
                if path.is_symlink():
                    continue
                os.chown(path, account.pw_uid, account.pw_gid, follow_symlinks=False)
                os.chmod(path, stat.S_IMODE(path.stat().st_mode) | stat.S_IRUSR | stat.S_IWUSR)
        os.setgroups([])
        os.setgid(account.pw_gid)
        os.setuid(account.pw_uid)
        os.environ['HOME'] = account.pw_dir
    if not os.access(directory, os.R_OK | os.W_OK | os.X_OK):
        raise RuntimeError('Redis cannot write /data; start the container with its default user '
                           'so startup can repair the mounted volume ownership')

def stop_process(process, timeout=10):
    if process is None:
        return
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()

def main():
    import redis

    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    shutdown_requested = False

    def shutdown(signum, frame):
        nonlocal shutdown_requested
        shutdown_requested = True

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    os.environ['REDIS_URL'] = 'redis://127.0.0.1:6379/0'
    redis_process = api_process = None
    client = redis.Redis(host='127.0.0.1', port=6379,
                         socket_connect_timeout=0.5, socket_timeout=0.5)
    try:
        prepare_runtime()
        redis_process = subprocess.Popen([
            'redis-server', '--bind', '127.0.0.1', '--port', '6379',
            '--protected-mode', 'yes', '--daemonize', 'no',
            '--appendonly', 'yes', '--appendfsync', 'everysec', '--dir', '/data',
        ])
        deadline = time.monotonic() + 15
        while not shutdown_requested:
            if redis_process.poll() is not None:
                raise RuntimeError('Redis exited during startup')
            try:
                if client.ping():
                    break
            except redis.exceptions.RedisError:
                pass
            if time.monotonic() >= deadline:
                raise RuntimeError('Redis did not become ready within 15 seconds')
            time.sleep(0.1)
        if shutdown_requested:
            return 0
        api_process = subprocess.Popen([
            sys.executable, '-m', 'uvicorn', 'app:app', '--host', '0.0.0.0',
            '--port', os.getenv('PORT', '10000'),
        ])
        while not shutdown_requested:
            for name, process in (('Redis', redis_process), ('API', api_process)):
                if process.poll() is not None:
                    logger.error('%s exited; stopping the container', name)
                    return 1
            time.sleep(0.2)
        return 0
    except Exception:
        logger.exception('Container startup failed')
        return 1
    finally:
        stop_process(api_process, timeout=15)
        stop_process(redis_process, timeout=10)
        client.close()

if __name__ == '__main__':
    sys.exit(main())

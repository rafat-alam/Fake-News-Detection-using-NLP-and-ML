"""Trusted operator CLI: python -m module.manage editor USERNAME [--revoke]."""
import argparse
from module.repo.user_repo import UserRepo

def main():
    parser = argparse.ArgumentParser(description='Grant or revoke editor access')
    parser.add_argument('command', choices=['editor'])
    parser.add_argument('username')
    parser.add_argument('--revoke', action='store_true')
    args = parser.parse_args()
    user = UserRepo.get_user(value=args.username.strip().lower(), search_by='username')
    if not user:
        parser.error('User not found; complete signup first')
    UserRepo.update_user(user.user_id, 'is_editor', not args.revoke)
    print(f'Editor access {"revoked" if args.revoke else "granted"} for {user.username}')

if __name__ == '__main__':
    main()

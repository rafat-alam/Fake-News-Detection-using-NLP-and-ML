"""Public author profiles never expose email addresses or password hashes."""
import uuid
from module.repo.user_repo import UserRepo
from module.services.auth_service import Response, service_result

class UserService:
    @staticmethod
    @service_result
    def get_author(user_id):
        user_id = str(uuid.UUID(str(user_id)))
        user = UserRepo.get_user(value=user_id, search_by='user_id')
        if not user:
            return Response(404, 'User not found')
        return Response(200, 'Author retrieved', {
            'user_id': str(user.user_id), 'username': user.username,
            'name': user.name, 'is_editor': user.is_editor,
        })

"""
User Access Handler for the app.
"""

from models import db, User
from datetime import datetime, timezone
from helpers import ResponseHelper, DateTimeNaiveHelper


class UserAccessHandler:
    @staticmethod
    def get_user_access(user_id):
        """
        Get user access status
        """

        user = db.session.get(User, user_id)
        if not user:
            return ResponseHelper.error("User not found", 404)

        access_status = {
            "user_id": user.id,
            "access_until": user.access_until.isoformat() if user.access_until else None,
            "has_access": DateTimeNaiveHelper.make_timezone_aware(user.access_until) > datetime.now(
                timezone.utc) if user.access_until else False
        }

        return ResponseHelper.success(access_status)

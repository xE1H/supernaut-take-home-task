"""
Helper functions for the app.
"""

from flask import jsonify
from datetime import timezone


class ResponseHelper:
    """
    Helper class for generating JSON responses.
    """

    @staticmethod
    def success(message):
        """
        Generate a success response.
        """
        if isinstance(message, dict):
            return jsonify(message), 200

        return jsonify({"message": message}), 200

    @staticmethod
    def error(message, status_code=400):
        """
        Generate an error response.
        """
        return jsonify({"error": message}), status_code


class DateTimeNaiveHelper:
    """
    Helper class for converting datetime objects to naive datetime.
    """

    @staticmethod
    def make_timezone_aware(dt):
        """Convert naive datetime to UTC timezone-aware datetime, since SQLAlchemy gives out naive datetimes by
        default."""
        if dt is None:
            return None
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt

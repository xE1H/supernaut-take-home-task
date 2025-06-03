"""
Helper functions for the app.
"""

from flask import jsonify


class ResponseHelper:
    """
    Helper class for generating JSON responses.
    """

    @staticmethod
    def success(message):
        """
        Generate a success response.
        """
        return jsonify({"message": message}), 200

    @staticmethod
    def error(message, status_code=400):
        """
        Generate an error response.
        """
        return jsonify({"error": message}), status_code
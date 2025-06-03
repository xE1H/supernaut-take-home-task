"""
API routes for the app
"""
from flask import Blueprint, request

from stripe_webhook_handler import StripeWebhookHandler
from user_access_handler import UserAccessHandler

api_bp = Blueprint('api', __name__)


@api_bp.route("/stripe/webhook", methods=["POST"])
def handle_stripe_webhook():
    """
    Stripe webhook endpoint
    Note: the stripe-signature header should be verified in production, but for this task I will skip that, since
    I am not using the actual Stripe API in any way.
    """
    event_data = request.json
    return StripeWebhookHandler.process_webhook_event(event_data)


@api_bp.route("/user/<int:user_id>/access", methods=["GET"])
def get_user_access(user_id):
    """
    Get user access status
    """

    return UserAccessHandler.get_user_access(user_id)

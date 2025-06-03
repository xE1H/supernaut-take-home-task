"""
Stripe webhook event handlers for the app
"""
from datetime import datetime, timezone, timedelta
from enum import Enum

from helpers import ResponseHelper
from models import db, User, StripeProcessedEvent


class StripeEventType(Enum):
    SUBSCRIPTION_CREATED = "customer.subscription.created"
    SUBSCRIPTION_UPDATED = "customer.subscription.updated"
    SUBSCRIPTION_DELETED = "customer.subscription.deleted"
    INVOICE_PAYMENT_FAILED = "invoice.payment_failed"
    INVOICE_PAID = "invoice.paid"


class SubscriptionStatus(Enum):
    ACTIVE = "active"
    TRIALING = "trialing"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    UNPAID = "unpaid"
    INCOMPLETE = "incomplete"
    INCOMPLETE_EXPIRED = "incomplete_expired"


RELEVANT_EVENTS = [event_type.value for event_type in StripeEventType]


class StripeWebhookHandler:

    @staticmethod
    def process_webhook_event(event_data):
        """
        Main webhook event processor that handles idempotent events and delegates event handling to specific handlers
        """
        event_id = event_data.get("id")

        if not event_id:
            return ResponseHelper.error("Invalid event data -- event id not found")

        # check if event was already processed for idempotency
        if StripeProcessedEvent.query.get(event_id):
            return ResponseHelper.success("Event already processed")

        # check if event type is relevant
        if event_data["type"] not in RELEVANT_EVENTS:
            return ResponseHelper.success("Event type not relevant, ignoring")

        try:
            # mark event as processed
            db.session.add(StripeProcessedEvent(stripe_event_id=event_id))

            # get or create user, for the sake of this task, users get created here if they don't exist
            user = StripeWebhookHandler._get_or_create_user(event_data)
            if not user:
                return ResponseHelper.error("Customer ID not found in event data")

            # handle the specific event type
            StripeWebhookHandler._handle_event_by_type(event_data, user)

            db.session.commit()
            return ResponseHelper.success(f"Event processed successfully for user id {user.id}")
            # Adding the ID here into the response just so I could pull that user ID later

        except Exception as e:
            db.session.rollback()
            return ResponseHelper.error(f"Failed to process event: {str(e)}", 500)

    @staticmethod
    def _get_or_create_user(event_data):
        """
        Get existing user or create new one based on Stripe customer ID
        """
        customer_id = event_data.get("data", {}).get("object", {}).get("customer")
        if not customer_id:
            return None

        user = User.query.filter_by(stripe_customer_id=customer_id).first()
        if not user:
            user = User(stripe_customer_id=customer_id)
            db.session.add(user)

        return user

    @staticmethod
    def _handle_event_by_type(event_data, user):
        """
        Route event to appropriate handler based on event type
        """
        event_type = event_data["type"]

        if event_type in [StripeEventType.SUBSCRIPTION_CREATED.value, StripeEventType.SUBSCRIPTION_UPDATED.value]:
            StripeWebhookHandler._handle_subscription_event(event_data, user)
        elif event_type == StripeEventType.SUBSCRIPTION_DELETED.value:
            StripeWebhookHandler._handle_subscription_deleted(user)
        elif event_type == StripeEventType.INVOICE_PAYMENT_FAILED.value:
            StripeWebhookHandler._handle_payment_failed(user)
        elif event_type == StripeEventType.INVOICE_PAID.value:
            StripeWebhookHandler._handle_invoice_paid(event_data, user)

    @staticmethod
    def _handle_subscription_event(event_data, user):
        """
        Handle subscription created/updated events
        """
        subscription = event_data.get("data", {}).get("object", {})
        status = subscription.get("status")

        if StripeWebhookHandler._is_active_subscription_status(status):
            # sub is active -- access until current period end
            current_period_end = subscription.get("current_period_end")
            user.access_until = datetime.fromtimestamp(current_period_end, tz=timezone.utc)

        elif status == SubscriptionStatus.PAST_DUE.value:
            # keep existing access until the end of the current period, a grace period could be implemented here
            pass
        else:  # canceled, unpaid, incomplete, incomplete_expired
            user.access_until = datetime.now(timezone.utc)

    @staticmethod
    def _is_active_subscription_status(status: str) -> bool:
        return status in [SubscriptionStatus.ACTIVE.value, SubscriptionStatus.TRIALING.value]

    @staticmethod
    def _handle_subscription_deleted(user):
        """
        Handle subscription deleted events
        """
        # instantly revoke access
        user.access_until = datetime.now(timezone.utc)

    @staticmethod
    def _handle_payment_failed(user):
        """
        Handle failed payment events
        """
        # instantly revoke access, a grace period could be implemented here
        user.access_until = datetime.now(timezone.utc)

    @staticmethod
    def _handle_invoice_paid(event_data, user):
        """
        Handle successful invoice payment events
        """
        invoice = event_data.get("data", {}).get("object", {})
        subscription_id = invoice.get("subscription")

        if subscription_id:
            # I believe that in this case, since the subscription object is not provided in the event,
            # the Stripe API should be called to retrieve the subscription details (to find out the current_period_end)
            # but for this task, I will assume that the subscription is active and set access until 30 days from now
            # Invoice object (Stripe): https://docs.stripe.com/api/invoices/object?api-version=2025-05-28.basil
            user.access_until = datetime.now(timezone.utc) + timedelta(days=30)

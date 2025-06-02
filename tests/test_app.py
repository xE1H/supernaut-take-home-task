import json
from unittest.mock import patch

from app import db, User, StripeProcessedEvent
from datetime import *


def create_subscription_event(event_id, event_type, customer_id, status="active", current_period_end=None):
    if current_period_end is None:
        current_period_end = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp())

    return json.dumps({
        "id": event_id,
        "type": event_type,
        "data": {
            "object": {
                "customer": customer_id,
                "status": status,
                "current_period_end": current_period_end
            }
        }
    })


def create_invoice_event(event_id, event_type, customer_id, subscription_id=None):
    invoice_data = {"customer": customer_id}
    if subscription_id:
        invoice_data["subscription"] = subscription_id

    return json.dumps({
        "id": event_id,
        "type": event_type,
        "data": {
            "object": invoice_data
        }
    })


def get_current_utc():
    """Helper to get current UTC time consistently"""
    return datetime.now(timezone.utc)


def make_timezone_aware(dt):
    """Convert naive datetime to UTC timezone-aware datetime, since SQLAlchemy gives out naive datetimes by default."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class TestStripeWebhook:
    def test_missing_event_id(self, client):
        response = client.post("/stripe/webhook", data=json.dumps({}), content_type='application/json')
        assert response.status_code == 400
        assert User.query.count() == 0

    def test_none_event_id(self, client):
        response = client.post("/stripe/webhook", data=json.dumps({"id": None}), content_type='application/json')
        assert response.status_code == 400
        assert User.query.count() == 0

    def test_missing_customer_id(self, client):
        response = client.post("/stripe/webhook", data=json.dumps({
            "id": "evt_123",
            "type": "customer.subscription.created",
            "data": {"object": {}}
        }), content_type='application/json')
        assert response.status_code == 400
        assert "Customer ID not found" in response.json["error"]
        assert User.query.count() == 0

    def test_none_customer_id(self, client):
        response = client.post("/stripe/webhook", data=json.dumps({
            "id": "evt_123",
            "type": "customer.subscription.created",
            "data": {"object": {"customer": None}}
        }), content_type='application/json')
        assert response.status_code == 400
        assert User.query.count() == 0

    def test_already_processed_event(self, client):
        event_data = create_subscription_event("evt_123", "customer.subscription.created", "cus_123")

        response1 = client.post("/stripe/webhook", data=event_data, content_type='application/json')
        assert response1.status_code == 200
        assert User.query.count() == 1
        assert StripeProcessedEvent.query.count() == 1

        response2 = client.post("/stripe/webhook", data=event_data, content_type='application/json')
        assert response2.status_code == 200
        assert response2.json["message"] == "Event already processed"
        assert User.query.count() == 1
        assert StripeProcessedEvent.query.count() == 1

    def test_subscription_created_active_status(self, client):
        future_time = int((get_current_utc() + timedelta(days=30)).timestamp())
        event_data = create_subscription_event("evt_123", "customer.subscription.created", "cus_123",
                                               "active", future_time)

        response = client.post("/stripe/webhook", data=event_data, content_type='application/json')
        assert response.status_code == 200

        user = User.query.first()
        assert user.stripe_customer_id == "cus_123"
        assert user.access_until is not None

        user_access_until = make_timezone_aware(user.access_until)
        assert user_access_until > get_current_utc()
        assert StripeProcessedEvent.query.count() == 1

    def test_subscription_created_trialing_status(self, client):
        future_time = int((get_current_utc() + timedelta(days=7)).timestamp())
        event_data = create_subscription_event("evt_123", "customer.subscription.created", "cus_123",
                                               "trialing", future_time)

        response = client.post("/stripe/webhook", data=event_data, content_type='application/json')
        assert response.status_code == 200

        user = User.query.first()
        assert user.stripe_customer_id == "cus_123"
        assert user.access_until is not None

        user_access_until = make_timezone_aware(user.access_until)
        assert user_access_until > get_current_utc()

    def test_subscription_created_past_due_status(self, client):
        future_time = int((get_current_utc() + timedelta(days=30)).timestamp())
        initial_event = create_subscription_event("evt_123", "customer.subscription.created", "cus_123",
                                                  "active", future_time)
        client.post("/stripe/webhook", data=initial_event, content_type='application/json')

        user = User.query.first()
        original_access = user.access_until

        past_due_event = create_subscription_event("evt_124", "customer.subscription.updated", "cus_123",
                                                   "past_due", future_time)
        response = client.post("/stripe/webhook", data=past_due_event, content_type='application/json')
        assert response.status_code == 200

        user = User.query.first()
        assert user.access_until == original_access  # should remain unchanged with past_due status

    def test_subscription_created_canceled_status(self, client):
        event_data = create_subscription_event("evt_123", "customer.subscription.created", "cus_123", "canceled")

        response = client.post("/stripe/webhook", data=event_data, content_type='application/json')
        assert response.status_code == 200

        user = User.query.first()
        assert user.stripe_customer_id == "cus_123"

        user_access_until = make_timezone_aware(user.access_until)
        assert user_access_until <= get_current_utc()

    def test_subscription_created_incomplete_status(self, client):
        event_data = create_subscription_event("evt_123", "customer.subscription.created", "cus_123", "incomplete")

        response = client.post("/stripe/webhook", data=event_data, content_type='application/json')
        assert response.status_code == 200

        user = User.query.first()
        user_access_until = make_timezone_aware(user.access_until)
        assert user_access_until <= get_current_utc()

    def test_subscription_updated_existing_user(self, client):
        user = User(stripe_customer_id="cus_123")
        with client.application.app_context():
            db.session.add(user)
            db.session.commit()

        future_time = int((get_current_utc() + timedelta(days=30)).timestamp())
        event_data = create_subscription_event("evt_123", "customer.subscription.updated", "cus_123",
                                               "active", future_time)

        response = client.post("/stripe/webhook", data=event_data, content_type='application/json')
        assert response.status_code == 200
        assert User.query.count() == 1  # Should not create new user

        user = User.query.first()
        assert user.access_until is not None

    def test_subscription_deleted(self, client):
        event_data = create_subscription_event("evt_123", "customer.subscription.created", "cus_123")
        client.post("/stripe/webhook", data=event_data, content_type='application/json')

        user = User.query.first()
        user_access_until = make_timezone_aware(user.access_until)
        assert user_access_until > get_current_utc()

        delete_event = json.dumps({
            "id": "evt_124",
            "type": "customer.subscription.deleted",
            "data": {
                "object": {
                    "customer": "cus_123"
                }
            }
        })

        response = client.post("/stripe/webhook", data=delete_event, content_type='application/json')
        assert response.status_code == 200

        user = User.query.first()
        user_access_until = make_timezone_aware(user.access_until)
        assert user_access_until <= get_current_utc()
        assert StripeProcessedEvent.query.count() == 2

    def test_invoice_payment_failed(self, client):
        event_data = create_subscription_event("evt_123", "customer.subscription.created", "cus_123")
        client.post("/stripe/webhook", data=event_data, content_type='application/json')

        user = User.query.first()
        user_access_until = make_timezone_aware(user.access_until)
        assert user_access_until > get_current_utc()

        # Now payment failed
        payment_failed_event = create_invoice_event("evt_124", "invoice.payment_failed", "cus_123")

        response = client.post("/stripe/webhook", data=payment_failed_event, content_type='application/json')
        assert response.status_code == 200

        user = User.query.first()
        user_access_until = make_timezone_aware(user.access_until)
        assert user_access_until <= get_current_utc()

    def test_invoice_paid_with_subscription(self, client):
        invoice_paid_event = create_invoice_event("evt_123", "invoice.paid", "cus_123", "sub_123")

        response = client.post("/stripe/webhook", data=invoice_paid_event, content_type='application/json')
        assert response.status_code == 200

        user = User.query.first()
        assert user.stripe_customer_id == "cus_123"

        expected_access = get_current_utc() + timedelta(days=30)
        user_access_until = make_timezone_aware(user.access_until)
        # allow for small time difference between server processing and test execution
        assert abs((user_access_until - expected_access).total_seconds()) < 5

    def test_invoice_paid_without_subscription(self, client):
        invoice_paid_event = create_invoice_event("evt_123", "invoice.paid", "cus_123")

        response = client.post("/stripe/webhook", data=invoice_paid_event, content_type='application/json')
        assert response.status_code == 200

        user = User.query.first()
        assert user.stripe_customer_id == "cus_123"
        assert user.access_until is None  # should remain None if no subscription

    def test_missing_subscription_data_for_subscription_event(self, client):
        event_data = json.dumps({
            "id": "evt_123",
            "type": "customer.subscription.created",
            "data": {}
        })

        response = client.post("/stripe/webhook", data=event_data, content_type='application/json')
        assert response.status_code == 400
        assert "Customer ID not found" in response.json["error"]

    def test_missing_subscription_object_for_subscription_event(self, client):
        event_data = json.dumps({
            "id": "evt_123",
            "type": "customer.subscription.created",
            "data": {
                "object": {
                    "customer": "cus_123"
                    # missing status and current_period_end
                }
            }
        })

        response = client.post("/stripe/webhook", data=event_data, content_type='application/json')
        assert response.status_code == 200  # should still work, status defaults to None which goes to else clause

        user = User.query.first()
        user_access_until = make_timezone_aware(user.access_until)
        assert user_access_until <= get_current_utc()

    def test_subscription_missing_data_object(self, client):
        event_data = json.dumps({
            "id": "evt_123",
            "type": "customer.subscription.created",
            "data": {
                "object": {
                    "customer": "cus_123"
                }
            }
        })

        response = client.post("/stripe/webhook", data=event_data, content_type='application/json')
        assert response.status_code == 200

        user = User.query.first()
        user_access_until = make_timezone_aware(user.access_until)
        assert user_access_until <= get_current_utc()

    def test_unknown_event_type(self, client):
        event_data = json.dumps({
            "id": "evt_123",
            "type": "some.unknown.event",
            "data": {
                "object": {
                    "customer": "cus_123"
                }
            }
        })

        response = client.post("/stripe/webhook", data=event_data, content_type='application/json')
        assert response.status_code == 200  # should still process and create user

        user = User.query.first()
        assert user.stripe_customer_id == "cus_123"
        assert user.access_until is None

    @patch('app.db.session.commit')
    def test_database_error_rollback(self, mock_commit, client):
        mock_commit.side_effect = Exception("Database error")

        event_data = create_subscription_event("evt_123", "customer.subscription.created", "cus_123")

        response = client.post("/stripe/webhook", data=event_data, content_type='application/json')
        assert response.status_code == 500
        assert "Failed to process event" in response.json["error"]

    def test_multiple_events_different_customers(self, client):
        event1 = create_subscription_event("evt_123", "customer.subscription.created", "cus_123")
        event2 = create_subscription_event("evt_124", "customer.subscription.created", "cus_456")

        response1 = client.post("/stripe/webhook", data=event1, content_type='application/json')
        response2 = client.post("/stripe/webhook", data=event2, content_type='application/json')

        assert response1.status_code == 200
        assert response2.status_code == 200
        assert User.query.count() == 2
        assert StripeProcessedEvent.query.count() == 2

    def test_subscription_status_edge_cases(self, client):
        event_data = create_subscription_event("evt_123", "customer.subscription.created", "cus_123", "unpaid")
        response = client.post("/stripe/webhook", data=event_data, content_type='application/json')
        assert response.status_code == 200

        user = User.query.first()
        user_access_until = make_timezone_aware(user.access_until)
        assert user_access_until <= get_current_utc()

        event_data2 = create_subscription_event("evt_124", "customer.subscription.updated", "cus_123",
                                                "incomplete_expired")
        response2 = client.post("/stripe/webhook", data=event_data2, content_type='application/json')
        assert response2.status_code == 200

        user = User.query.first()
        user_access_until = make_timezone_aware(user.access_until)
        assert user_access_until <= get_current_utc()

    def test_subscription_created_missing_subscription_data(self, client):
        event_data = json.dumps({
            "id": "evt_123",
            "type": "customer.subscription.created",
            "data": {
                "object": {
                    "customer": "cus_123"
                }
            }
        })

        response = client.post("/stripe/webhook", data=event_data, content_type='application/json')
        assert response.status_code == 200

        user = User.query.first()
        assert user.stripe_customer_id == "cus_123"

        user_access_until = make_timezone_aware(user.access_until)
        assert user_access_until <= get_current_utc()

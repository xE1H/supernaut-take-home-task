import json
from app import User, StripeProcessedEvent

STRIPE_SUBSCRIPTION_CREATED_REQUEST = json.dumps({
    "id": "evt_123",
    "type": "customer.subscription.created",
    "data": {
        "object": {
            "customer": "cus_123"
        }
    }
})

STRIPE_SUBSCRIPTION_UPDATED_REQUEST = json.dumps({
    "id": "evt_456",
    "type": "customer.subscription.updated",
    "data": {
        "object": {
            "customer": "cus_123"
        }
    }
})

STRIPE_SUBSCRIPTION_DELETED_REQUEST = json.dumps({
    "id": "evt_456",
    "type": "customer.subscription.deleted",
    "data": {
        "object": {
            "customer": "cus_123"
        }
    }
})


class TestStripeWebhook:
    def test_missing_data(self, client):
        response = client.post("/stripe/webhook", data=json.dumps({}), content_type='application/json')
        assert response.status_code == 400

        assert User.query.count() == 0

    def test_missing_customer_id(self, client):
        response = client.post("/stripe/webhook", data=json.dumps(
            {"id": "evt_123", "type": "customer.subscription.created", "data": {"object": {}}}),
                               content_type='application/json')
        assert response.status_code == 400

        assert User.query.count() == 0

    def test_none_customer_id(self, client):
        response = client.post("/stripe/webhook", data=json.dumps(
            {"id": "evt_123", "type": "customer.subscription.created", "data": {"object": {"customer": None}}}),
                               content_type='application/json')
        assert response.status_code == 400

        assert User.query.count() == 0

    def test_already_processed_event(self, client):
        response1 = client.post("/stripe/webhook", data=STRIPE_SUBSCRIPTION_CREATED_REQUEST,
                                content_type='application/json')
        assert response1.status_code == 200
        assert User.query.count() == 1
        assert StripeProcessedEvent.query.count() == 1

        response2 = client.post("/stripe/webhook", data=STRIPE_SUBSCRIPTION_CREATED_REQUEST,
                                content_type='application/json')
        assert response2.status_code == 200
        assert User.query.count() == 1
        assert StripeProcessedEvent.query.count() == 1

    def test_created_request(self, client):
        response = client.post("/stripe/webhook", data=STRIPE_SUBSCRIPTION_CREATED_REQUEST,
                               content_type='application/json')
        assert response.status_code == 200

        user = User.query.first()
        assert user.stripe_customer_id == "cus_123"
        assert user.has_access is True
        assert StripeProcessedEvent.query.count() == 1

    def test_deleted_request(self, client):
        client.post("/stripe/webhook", data=STRIPE_SUBSCRIPTION_CREATED_REQUEST,
                    content_type='application/json')
        user = User.query.first()
        assert user.stripe_customer_id == "cus_123"
        assert user.has_access is True

        response = client.post("/stripe/webhook", data=STRIPE_SUBSCRIPTION_DELETED_REQUEST,
                               content_type='application/json')
        assert response.status_code == 200

        user = User.query.first()
        assert user.stripe_customer_id == "cus_123"
        assert user.has_access is False
        assert StripeProcessedEvent.query.count() == 2

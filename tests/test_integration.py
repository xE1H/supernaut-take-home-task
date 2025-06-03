from tests.conftest import *


class TestIntegration:
    def test_webhook_creates_user_then_get_access(self, client):
        """Test full flow: webhook creates user with access, then get access returns correct status"""
        future_time = get_30_days_later()
        event_data = create_subscription_event("evt_123", "customer.subscription.created",
                                               "cus_123", "active", future_time)

        # webhook creates user
        webhook_response = client.post("/stripe/webhook", data=event_data, content_type='application/json')
        assert webhook_response.status_code == 200

        # extract user ID from response
        user_id = int(webhook_response.json["message"].split("user id ")[1])

        # get user access
        access_response = client.get(f"/user/{user_id}/access")
        assert access_response.status_code == 200

        data = access_response.json
        assert data["user_id"] == user_id
        assert data["has_access"]
        assert data["access_until"] is not None

    def test_webhook_creates_user_with_expired_access_then_get_access(self, client):
        """Test full flow: webhook creates user with canceled subscription, then get access shows no access"""
        event_data = create_subscription_event("evt_123", "customer.subscription.created",
                                               "cus_123", "canceled")

        # webhook creates user with no access
        webhook_response = client.post("/stripe/webhook", data=event_data, content_type='application/json')
        assert webhook_response.status_code == 200

        user_id = int(webhook_response.json["message"].split("user id ")[1])

        # get user access
        access_response = client.get(f"/user/{user_id}/access")
        assert access_response.status_code == 200

        data = access_response.json
        assert data["user_id"] == user_id
        assert not data["has_access"]
        assert data["access_until"] is not None  # should have timestamp but in the past

    def test_webhook_updates_existing_user_access_then_get_access(self, client):
        """Test full flow: multiple webhooks update same user, final access status is correct"""
        # create user with active subscription
        future_time = get_30_days_later()
        create_event = create_subscription_event("evt_123", "customer.subscription.created",
                                                 "cus_123", "active", future_time)

        webhook_response1 = client.post("/stripe/webhook", data=create_event, content_type='application/json')
        assert webhook_response1.status_code == 200
        user_id = int(webhook_response1.json["message"].split("user id ")[1])

        # verify user has access
        access_response1 = client.get(f"/user/{user_id}/access")
        assert access_response1.json["has_access"]

        # subscription gets deleted
        delete_event = create_bare_event("evt_124", "customer.subscription.deleted",
                                         "cus_123")

        event_data = create_bare_event("evt_123", "customer.subscription.created",
                                       "cus_123")
        webhook_response2 = client.post("/stripe/webhook", data=delete_event, content_type='application/json')
        assert webhook_response2.status_code == 200

        # verify user now has no access
        access_response2 = client.get(f"/user/{user_id}/access")
        assert access_response2.status_code == 200
        assert not access_response2.json["has_access"]

    def test_multiple_users_integration(self, client):
        """Test creating multiple users via webhooks and getting their individual access statuses"""
        # create first user with active subscription
        future_time = get_30_days_later()
        event1 = create_subscription_event("evt_123", "customer.subscription.created",
                                           "cus_123", "active", future_time)

        response1 = client.post("/stripe/webhook", data=event1, content_type='application/json')
        user1_id = int(response1.json["message"].split("user id ")[1])

        # create second user with canceled subscription
        event2 = create_subscription_event("evt_124", "customer.subscription.created",
                                           "cus_456", "canceled")

        response2 = client.post("/stripe/webhook", data=event2, content_type='application/json')
        user2_id = int(response2.json["message"].split("user id ")[1])

        # verify first user has access
        access1 = client.get(f"/user/{user1_id}/access")
        assert access1.json["has_access"]

        # verify second user has no access
        access2 = client.get(f"/user/{user2_id}/access")
        assert not access2.json["has_access"]

        # verify users are different
        assert user1_id != user2_id

    def test_payment_failed_then_paid_integration(self, client):
        """Test full flow: user has access, payment fails (access revoked), then payment succeeds (access restored)"""
        # create user with active subscription
        future_time = get_30_days_later()
        create_event = create_subscription_event("evt_123", "customer.subscription.created",
                                                 "cus_123", "active", future_time)

        response1 = client.post("/stripe/webhook", data=create_event, content_type='application/json')
        user_id = int(response1.json["message"].split("user id ")[1])

        # verify user has access
        access1 = client.get(f"/user/{user_id}/access")
        assert access1.json["has_access"]

        # payment fails
        payment_failed_event = create_invoice_event("evt_124", "invoice.payment_failed",
                                                    "cus_123")
        response2 = client.post("/stripe/webhook", data=payment_failed_event, content_type='application/json')
        assert response2.status_code == 200

        # verify user now has no access
        access2 = client.get(f"/user/{user_id}/access")
        assert not access2.json["has_access"]

        # payment succeeds
        payment_success_event = create_invoice_event("evt_125", "invoice.paid",
                                                     "cus_123", "sub_123")
        response3 = client.post("/stripe/webhook", data=payment_success_event, content_type='application/json')
        assert response3.status_code == 200

        # verify user has access again
        access3 = client.get(f"/user/{user_id}/access")
        assert access3.json["has_access"]

    def test_invoice_paid_without_subscription_integration(self, client):
        """Test invoice paid event without subscription doesn't grant access"""
        # invoice paid without subscription
        invoice_event = create_invoice_event("evt_123", "invoice.paid", "cus_123")

        response1 = client.post("/stripe/webhook", data=invoice_event, content_type='application/json')
        assert response1.status_code == 200
        user_id = int(response1.json["message"].split("user id ")[1])

        # verify user has no access since no subscription was involved
        access_response = client.get(f"/user/{user_id}/access")
        assert not access_response.json["has_access"]
        assert access_response.json["access_until"] is None

    def test_webhook_error_doesnt_create_user_then_get_access_fails(self, client):
        """Test that failed webhook doesn't create user, and subsequent access check fails"""
        # send webhook with missing customer ID
        invalid_event = json.dumps({
            "id": "evt_123",
            "type": "customer.subscription.created",
            "data": {"object": {}}
        })

        response1 = client.post("/stripe/webhook", data=invalid_event, content_type='application/json')
        assert response1.status_code == 400
        assert User.query.count() == 0

        # try to get access for non-existent user
        access_response = client.get("/user/1/access")
        assert access_response.status_code == 404

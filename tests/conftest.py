import json
from datetime import *

import pytest

from app import app, db
from models import User


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


def create_bare_event(event_id, event_type, customer_id):
    return json.dumps({
        "id": event_id,
        "type": event_type,
        "data": {
            "object": {
                "customer": customer_id
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


def create_user(client, access_until):
    user = User(stripe_customer_id="cus_123", access_until=access_until)

    with client.application.app_context():
        db.session.add(user)
        db.session.commit()
        return user.id


def get_current_utc():
    """Helper to get current UTC time consistently"""
    return datetime.now(timezone.utc)


def get_30_days_later():
    """Helper to get current UTC time plus 30 days"""
    return int((get_current_utc() + timedelta(days=30)).timestamp())


@pytest.fixture
def client():
    """
    Create the test client for the app.
    """
    app.config['TESTING'] = True

    with app.test_client() as client:
        with app.app_context():
            db.create_all()
            yield client
            db.session.remove()
            db.drop_all()

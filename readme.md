# Supernaut Take Home Task

- [Quick start](#quick-start)
- [Database](#database)
- [Project structure](#project-structure)
- [Data structures](#data-structures)
- [Webhook event handling](#webhook-event-handling)
- [API endpoints](#api-endpoints)
- [Testing](#testing)
- [Design considerations](#design-considerations)
- [Example webhook payloads & testing w/ Postman](#example-webhook-payloads)

## Quick start

Prerequisites:

- Python 3.11
- pip

### Installation

```shell
# Install required dependencies
python3 -m pip install -r requirements.txt

# Run the app
python3 app.py
```

## Database

The app uses SQLite for simplicity for this task. Since it is all running on SQLAlchemy, the database could easily be
exchanged for Postgres or another SQL database if needed. The SQLite file is created automatically upon startup.

## Project structure

```sh
├── app.py                         # Flask application entry point
├── config.py                      # Configuration settings
├── models.py                      # Database models
├── routes.py                      # API route definitions
├── helpers.py                     # Utility functions
├── requirements.txt               # Python dependencies
├── requirements-test.txt          # Python dependencies for running tests
├── handlers/                      # Handlers for business logic
|   ├── stripe_webhook_handler.py  # Webhook event processing logic
|   └── user_access_handler.py     # User access management
└── tests/                         # Test files
    ├── __init__.py            
    ├── conftest.py                # Test fixtures and helpers
    ├── test_stripe_webhook.py     # Webhook handler tests
    ├── test_user_access.py        # User access tests
    └── test_integration.py        # E2E tests
```

## Data structures

### User model

```python
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    stripe_customer_id = db.Column(db.String(100), unique=True, nullable=False)
    access_until = db.Column(db.DateTime, nullable=True)
```

**Purpose:** Represents a user in the system, linked to their Stripe customer ID and subscription access expiration
date.

**Fields:**

- `id`: Unique identifier for the user.
- `stripe_customer_id`: The Stripe customer ID associated with the user.
- `access_until`: The date and time until which the user has access to the system. If `None`, the user has no access.

### StripeProcessedEvent model

```python
class StripeProcessedEvent(db.Model):
    stripe_event_id = db.Column(db.String(100), primary_key=True)
```

**Purpose:** Tracks Stripe events that have been processed to avoid duplicate processing.

**Fields:**

- `stripe_event_id`: Unique identifier for the Stripe event. This is used to ensure that each event is processed only
  once.

## Webhook event handling

The app processes the following Stripe webhook events to maintain subscription status:

1. `customer.subscription.created` & `customer.subscription.updated`

   **Purpose:** Handle new subscriptions and subscription changes.

   **Logic:**
    - `active`/`trialing`: Grant access until `current_period_end`
    - `past_due`: Maintain existing `access_until`, but do not extend access. A grace period of a couple of days could
      be implemented here for better UX.
    - `canceled`/`unpaid`/`incomplete`: Revoke access immediately. Just like `past_due`, a grace period could be
      implemented here for some of the states.

2. `customer.subscription.deleted`

   Purpose: Handle subscription cancellations.

   Logic: Immediately revoke access by setting `access_until` to current time.
3. `invoice.payment_failed`

   Purpose: Handle failed payments.

   Logic: Immediately revoke access (could be extended with grace periods).
4. `invoice.paid`

   Purpose: Handle successful payments.

   Logic:
    - If linked to subscription: Restore access for 30 days (simplified, since the Stripe `Invoice` object does not have
      the subscription object in it, and an API call would be required to retrieve it here).
    - If standalone invoice: No access change.

### General event processing flow

1. Check for idempotency by checking if the event ID has already been processed.
2. If not processed, check if the event is relevant to the app.
3. Get the user by their Stripe customer ID (or create a new one for the sake of this app, since there's no real user
   management system).
4. Handle event based on its type.
5. Commit changes to the database. If something goes wrong, send 500 response to Stripe to retry the event later.

## API endpoints

**POST** `/stripe/webhook`

**Purpose:** Handle Stripe webhook events.

**Request body:** JSON payload from Stripe.

**Response:**

- `200 OK`: Event processed successfully.
- `400 Bad Request`: Invalid event type or missing data.
- `500 Internal Server Error`: Error processing the event.

**GET** `/user/<user_id>/access`

**Purpose:** Check user access status.

**Path parameter:** `user_id` - The ID of the user to check access for.

**Response:**

- `200 OK`: User access status.
    - Returns `{"user_id": <user_id>, "access_until": "<datetime>", "has_access": <bool>}`.
- `404 Not Found`: User not found.

## Testing

### Running tests

```sh
# Install testing dependencies
python3 -m pip install -r requirements-test.txt

# Run tests with coverage report
pytest --cov=.
```

### Test coverage

I have covered all the business logic with unit tests, including:

- 20+ tests for the webhook handler covering all event types, edge cases, error handling and DB rollback.
- 8 tests for user access management covering valid and expired access cases, edge cases and error handling.
- 7 E2E tests covering complete workflows.

## Design considerations

I have made some assumptions during the development process:

- I have assumed that there is only one single subscription per user, and that the subscription is
  linked to the user by their Stripe customer ID.
- I have assumed that Stripe events may be idempotent, and that the app should handle them accordingly.
- I have assumed that Stripe events arrive in the order they were created, and that the app should process them in that
  order. I do realise that in production this may not be the case -- and some sort of mitigation for this should be
  implemented.
- I have assumed that there are no grace periods -- the moment a subscription is canceled or a payment fails,
  the user loses access immediately. This could be extended with grace periods for better UX.

### Limitations

- I believe that for a full implementation, the app should have access to the Stripe API to fetch `Subscription` objects
  when they are not provided (ex. in the `invoice.paid` event). Currently, the app just sets a time 30 days into the
  future as the expiry time in this case.
- In production, webhooks should have their signature verified.

### Design choices

- All business logic is implemented in the `stripe_webhook_handler.py` file, which processes the events and updates
  user access accordingly.
- All user state changes are driven by events coming from Stripe, ensuring that no user state is changed without a
  corresponding event.
- All database transactions are atomic, ensuring that if something goes wrong, the database is rolled back to a
  consistent state.
- In general, the app has a fail-safe approach, meaning that if something goes wrong, the app will not
  change the user state and will return an error to Stripe to retry the event later.

### Scalability considerations

- The app is completely stateless, meaning that it can be easily scaled horizontally by adding more instances.
- The `User` model could also be indexed on `stripe_customer_id` for faster lookups.

## Example webhook payloads

### Subscription Created (Active)

```json
{
  "id": "evt_1234567890",
  "type": "customer.subscription.created",
  "data": {
    "object": {
      "customer": "cus_customer123",
      "status": "active",
      "current_period_end": 1740384000
    }
  }
}
```

### Subscription Updated (Canceled)

```json
{
  "id": "evt_1234567891",
  "type": "customer.subscription.updated",
  "data": {
    "object": {
      "customer": "cus_customer123",
      "status": "canceled",
      "current_period_end": 1740384000
    }
  }
}
```

### Subscription Deleted

```json
{
  "id": "evt_1234567892",
  "type": "customer.subscription.deleted",
  "data": {
    "object": {
      "customer": "cus_customer123"
    }
  }
}
```

### Payment Failed

```json
{
  "id": "evt_1234567893",
  "type": "invoice.payment_failed",
  "data": {
    "object": {
      "customer": "cus_customer123"
    }
  }
}
```

### Invoice Paid

```json
{
  "id": "evt_1234567894",
  "type": "invoice.paid",
  "data": {
    "object": {
      "customer": "cus_customer123",
      "subscription": "sub_subscription123"
    }
  }
}
```

### Testing with Postman

1. Start the application (`python app.py`)
2. Send POST requests to `http://localhost:5000/stripe/webhook`.
3. Use the example payloads above as request body (but any Stripe webhook payload should work).
4. Check user access with GET `http://localhost:5000/user/{user_id}/access`.



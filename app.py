"""
Supernaut Take Home Task
Nojus Adomaitis, 2025
"""
from datetime import *

from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///supernaut.db'  # sqlite here for simplicity

db = SQLAlchemy(app)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    stripe_customer_id = db.Column(db.String(100), unique=True, nullable=False)
    access_until = db.Column(db.DateTime, nullable=True)


class StripeProcessedEvent(db.Model):
    stripe_event_id = db.Column(db.String(100), primary_key=True)


@app.route("/stripe/webhook", methods=["POST"])
def handle_stripe_webhook():
    # the stripe-signature header should be verified in production, but for this task I will skip that
    event_data = request.json

    event_id = event_data.get("id")

    if not event_id:
        return jsonify({"error": "Invalid event data -- event id not found"}), 400

    if StripeProcessedEvent.query.get(event_id):
        return jsonify({"message": "Event already processed"}), 200

    db.session.add(StripeProcessedEvent(stripe_event_id=event_id))

    customer_id = event_data.get("data", {}).get("object", {}).get("customer")
    if not customer_id:
        return jsonify({"error": "Customer ID not found in event data"}), 400

    user = User.query.filter_by(stripe_customer_id=customer_id).first()
    if not user:
        user = User(stripe_customer_id=customer_id)
        db.session.add(user)

    if event_data["type"] == "customer.subscription.created" or event_data["type"] == "customer.subscription.updated":
        subscription = event_data.get("data", {}).get("object", {})
        if not subscription:
            return jsonify({"error": "Subscription data not found in event"}), 400

        status = subscription.get("status")

        if status in ["active", "trialing"]:
            # sub is active -- access until current period end
            current_period_end = subscription.get("current_period_end")
            if current_period_end:
                user.access_until = datetime.fromtimestamp(current_period_end, tz=timezone.utc)
            else:
                # fallback to 30 days from now if current_period_end is not provided (shouldn't happen)
                user.access_until = datetime.now(timezone.utc) + timedelta(days=30)

        elif status in ["past_due"]:
            # keep existing access until the end of the current period
            pass
        else:  # canceled, unpaid, incomplete, incomplete_expired
            user.access_until = datetime.now(timezone.utc)

    elif event_data["type"] == "customer.subscription.deleted":
        user.access_until = datetime.now(timezone.utc)

    # TODO - figure out if invoice events should be handled here (payment_failed, paid?)
    # TODO - subscription paused and resumed events?
    # TODO - grace period? current impl assumes immediate access removal

    try:
        db.session.commit()
        return jsonify({"message": "Event processed successfully"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Failed to process event: {str(e)}"}), 500


if __name__ == "__main__":
    app.run(debug=True)

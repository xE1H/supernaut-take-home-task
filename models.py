"""
Database models for the app
"""
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    stripe_customer_id = db.Column(db.String(100), unique=True, nullable=False)
    access_until = db.Column(db.DateTime, nullable=True)


class StripeProcessedEvent(db.Model):
    stripe_event_id = db.Column(db.String(100), primary_key=True)

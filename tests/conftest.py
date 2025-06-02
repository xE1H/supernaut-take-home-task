import pytest
import tempfile
import os

from flask_sqlalchemy import SQLAlchemy

from app import app, db


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

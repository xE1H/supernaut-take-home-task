import pytest
import tempfile
import os

from app import app, db, User, StripeProcessedEvent


@pytest.fixture
def client():
    """
    Create the test client for the app with a temp db.
    """
    temp_db_file_descriptor, temp_db_path = tempfile.mkstemp()
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{temp_db_path}'
    app.config['TESTING'] = True

    with app.test_client() as client:
        with app.app_context():
            db.create_all()
            yield client
            db.drop_all()

    os.close(temp_db_file_descriptor)
    os.unlink(temp_db_path)
from tests.conftest import *


class TestUserAccessHandler:
    def test_get_user_access_with_valid_access(self, client):
        """Test getting access for user with future access_until date"""
        future_time = get_current_utc() + timedelta(days=10)
        user_id = create_user(client, future_time)

        response = client.get(f"/user/{user_id}/access")
        assert response.status_code == 200

        data = response.json
        assert data["user_id"] == user_id
        assert data["has_access"]
        assert data["access_until"] is not None

    def test_get_user_access_with_expired_access(self, client):
        """Test getting access for user with past access_until date"""
        past_time = get_current_utc() - timedelta(days=1)
        user_id = create_user(client, past_time)

        response = client.get(f"/user/{user_id}/access")
        assert response.status_code == 200

        data = response.json
        assert data["user_id"] == user_id
        assert not data["has_access"]
        assert data["access_until"] is not None

    def test_get_user_access_with_no_access_until(self, client):
        """Test getting access for user with no access_until set"""
        user_id = create_user(client, None)

        response = client.get(f"/user/{user_id}/access")
        assert response.status_code == 200

        data = response.json
        assert data["user_id"] == user_id
        assert not data["has_access"]
        assert data["access_until"] is None

    def test_get_user_access_user_not_found(self, client):
        """Test getting access for non-existent user"""
        response = client.get("/user/999/access")
        assert response.status_code == 404
        assert "User not found" in response.json["error"]

    def test_get_user_access_with_access_exactly_now(self, client):
        """Test edge case where access_until is exactly current time"""
        current_time = get_current_utc()
        user_id = create_user(client, current_time)

        response = client.get(f"/user/{user_id}/access")
        assert response.status_code == 200

        data = response.json
        assert data["user_id"] == user_id
        # should be False since access_until is not > current time
        assert not data["has_access"]

    def test_get_user_access_invalid_user_id(self, client):
        """Test getting access with invalid user ID format"""
        response = client.get("/user/invalid_id/access")
        assert response.status_code == 404  # Flask converts invalid int to 404

    def test_get_user_access_zero_user_id(self, client):
        """Test getting access with user ID of 0"""
        response = client.get("/user/0/access")
        assert response.status_code == 404

    def test_get_user_access_negative_user_id(self, client):
        """Test getting access with negative user ID"""
        response = client.get("/user/-1/access")
        assert response.status_code == 404

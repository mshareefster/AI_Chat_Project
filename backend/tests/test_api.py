
def test_health_endpoint(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_models_endpoint(client):
    response = client.get("/api/models")

    assert response.status_code == 200
    assert "models" in response.json()
    assert len(response.json()["models"]) > 0


def test_auth_me_without_cookie(client):
    response = client.get("/api/auth/me")

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated."


def test_create_conversation_without_login(client):
    response = client.post("/api/conversations")

    assert response.status_code == 401


def test_list_conversations_without_login(client):
    response = client.get("/api/conversations")

    assert response.status_code == 401


def test_chat_without_login(client):
    response = client.post(
        "/api/chat",
        data={
            "conversationId": "507f1f77bcf86cd799439011",
            "model": "claude-fable-5",
            "message": "Hello"
        }
    )

    assert response.status_code == 401


def test_signup_success(client):
    response = client.post(
        "/api/auth/signup",
        json={
            "name": "Test User",
            "email": "test@example.com",
            "password": "password123"
        }
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Account created successfully."
    assert response.json()["user"]["email"] == "test@example.com"


def test_signup_invalid_email(client):
    response = client.post(
        "/api/auth/signup",
        json={
            "name": "Test User",
            "email": "invalid-email",
            "password": "password123"
        }
    )

    assert response.status_code == 422


def test_signup_short_password(client):
    response = client.post(
        "/api/auth/signup",
        json={
            "name": "Test User",
            "email": "test@example.com",
            "password": "123"
        }
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Password must be at least 8 characters."


def test_signup_duplicate_email(client):
    payload = {
        "name": "Test User",
        "email": "test@example.com",
        "password": "password123"
    }

    first_response = client.post("/api/auth/signup", json=payload)
    second_response = client.post("/api/auth/signup", json=payload)

    assert first_response.status_code == 200
    assert second_response.status_code == 409


def test_login_success(client):
    signup_response = client.post(
        "/api/auth/signup",
        json={
            "name": "Test User",
            "email": "test@example.com",
            "password": "password123"
        }
    )

    assert signup_response.status_code == 200

    response = client.post(
        "/api/auth/login",
        json={
            "email": "test@example.com",
            "password": "password123"
        }
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Login successful."
    assert "huda_session" in response.cookies


def test_login_wrong_password(client):
    client.post(
        "/api/auth/signup",
        json={
            "name": "Test User",
            "email": "test@example.com",
            "password": "password123"
        }
    )

    response = client.post(
        "/api/auth/login",
        json={
            "email": "test@example.com",
            "password": "wrongpassword"
        }
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password."


def test_session_validation_after_login(client):
    client.post(
        "/api/auth/signup",
        json={
            "name": "Session User",
            "email": "session@example.com",
            "password": "password123"
        }
    )

    login_response = client.post(
        "/api/auth/login",
        json={
            "email": "session@example.com",
            "password": "password123"
        }
    )

    assert login_response.status_code == 200

    response = client.get("/api/auth/me")

    assert response.status_code == 200
    assert response.json()["user"]["email"] == "session@example.com"


def test_logout(client):
    client.post(
        "/api/auth/signup",
        json={
            "name": "Logout User",
            "email": "logout@example.com",
            "password": "password123"
        }
    )

    client.post(
        "/api/auth/login",
        json={
            "email": "logout@example.com",
            "password": "password123"
        }
    )

    logout_response = client.post("/api/auth/logout")

    assert logout_response.status_code == 200
    assert logout_response.json()["message"] == "Logged out successfully."

    response = client.get("/api/auth/me")

    assert response.status_code == 401

def create_logged_in_user(client, name="Test User", email="test@example.com"):
    signup_response = client.post(
        "/api/auth/signup",
        json={
            "name": name,
            "email": email,
            "password": "password123"
        }
    )

    assert signup_response.status_code == 200

    login_response = client.post(
        "/api/auth/login",
        json={
            "email": email,
            "password": "password123"
        }
    )

    assert login_response.status_code == 200


def test_create_conversation_after_login(client):
    create_logged_in_user(client)

    response = client.post("/api/conversations")

    assert response.status_code == 200

    conversation = response.json()["conversation"]

    assert conversation["title"] == "New chat"
    assert conversation["id"]
    assert conversation["messages"] == []


def test_list_conversations_after_login(client):
    create_logged_in_user(client)

    client.post("/api/conversations")
    client.post("/api/conversations")

    response = client.get("/api/conversations")

    assert response.status_code == 200
    assert len(response.json()["conversations"]) == 2


def test_get_conversation_by_id(client):
    create_logged_in_user(client)

    create_response = client.post("/api/conversations")
    conversation_id = create_response.json()["conversation"]["id"]

    response = client.get(f"/api/conversations/{conversation_id}")

    assert response.status_code == 200
    assert response.json()["conversation"]["id"] == conversation_id
    assert response.json()["conversation"]["title"] == "New chat"


def test_get_conversation_invalid_id(client):
    create_logged_in_user(client)

    response = client.get("/api/conversations/invalid-id")

    assert response.status_code == 400


def test_rename_conversation(client):
    create_logged_in_user(client)

    create_response = client.post("/api/conversations")
    conversation_id = create_response.json()["conversation"]["id"]

    response = client.patch(
        f"/api/conversations/{conversation_id}",
        json={"title": "My AI Chat"}
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Conversation renamed successfully."

    get_response = client.get(f"/api/conversations/{conversation_id}")

    assert get_response.json()["conversation"]["title"] == "My AI Chat"


def test_rename_conversation_empty_title(client):
    create_logged_in_user(client)

    create_response = client.post("/api/conversations")
    conversation_id = create_response.json()["conversation"]["id"]

    response = client.patch(
        f"/api/conversations/{conversation_id}",
        json={"title": "   "}
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Title cannot be empty."


def test_rename_conversation_long_title(client):
    create_logged_in_user(client)

    create_response = client.post("/api/conversations")
    conversation_id = create_response.json()["conversation"]["id"]

    response = client.patch(
        f"/api/conversations/{conversation_id}",
        json={"title": "A" * 101}
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Title is too long."


def test_delete_conversation(client):
    create_logged_in_user(client)

    create_response = client.post("/api/conversations")
    conversation_id = create_response.json()["conversation"]["id"]

    response = client.delete(f"/api/conversations/{conversation_id}")

    assert response.status_code == 200
    assert response.json()["message"] == "Conversation deleted successfully."

    get_response = client.get(f"/api/conversations/{conversation_id}")

    assert get_response.status_code == 404


def test_user_cannot_access_another_users_conversation(client):
    create_logged_in_user(
        client,
        name="First User",
        email="first@example.com"
    )

    create_response = client.post("/api/conversations")
    conversation_id = create_response.json()["conversation"]["id"]

    client.post("/api/auth/logout")

    create_logged_in_user(
        client,
        name="Second User",
        email="second@example.com"
    )

    response = client.get(f"/api/conversations/{conversation_id}")

    assert response.status_code == 404

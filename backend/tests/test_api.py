
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


def complete_signup(
    client,
    sent_otps,
    name="Test User",
    email="test@example.com",
):
    signup_response = client.post(
        "/api/auth/signup",
        json={
            "name": name,
            "email": email,
            "password": "password123"
        }
    )

    assert signup_response.status_code == 200

    otp = sent_otps[-1]["otp"]

    verify_response = client.post(
        "/api/auth/signup/verify",
        json={
            "email": email,
            "otp": otp
        }
    )

    assert verify_response.status_code == 200

    return verify_response


def create_logged_in_user(
    client,
    sent_otps,
    name="Test User",
    email="test@example.com"
):
    complete_signup(
        client,
        sent_otps,
        name=name,
        email=email
    )

    login_response = client.post(
        "/api/auth/login",
        json={
            "email": email,
            "password": "password123"
        }
    )

    assert login_response.status_code == 200

    otp = sent_otps[-1]["otp"]

    verify_response = client.post(
        "/api/auth/login/verify",
        json={
            "email": email,
            "otp": otp
        }
    )

    assert verify_response.status_code == 200
    assert "huda_session" in verify_response.cookies

    return verify_response


def test_signup_success(client, sent_otps):
    response = client.post(
        "/api/auth/signup",
        json={
            "name": "Test User",
            "email": "test@example.com",
            "password": "password123"
        }
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Verification OTP sent to your email."
    assert sent_otps[-1]["purpose"] == "signup"

    verify_response = client.post(
        "/api/auth/signup/verify",
        json={
            "email": "test@example.com",
            "otp": sent_otps[-1]["otp"]
        }
    )

    assert verify_response.status_code == 200
    assert verify_response.json()["message"] == "Account created successfully."
    assert verify_response.json()["user"]["email"] == "test@example.com"


def test_signup_does_not_create_user_before_verification(client, sent_otps):
    response = client.post(
        "/api/auth/signup",
        json={
            "name": "Test User",
            "email": "pending@example.com",
            "password": "password123"
        }
    )

    assert response.status_code == 200

    login_response = client.post(
        "/api/auth/login",
        json={
            "email": "pending@example.com",
            "password": "password123"
        }
    )

    assert login_response.status_code == 401


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


def test_signup_duplicate_email(client, sent_otps):
    complete_signup(client, sent_otps)

    second_response = client.post(
        "/api/auth/signup",
        json={
            "name": "Test User",
            "email": "test@example.com",
            "password": "password123"
        }
    )

    assert second_response.status_code == 409


def test_signup_wrong_otp(client, sent_otps):
    client.post(
        "/api/auth/signup",
        json={
            "name": "Test User",
            "email": "wrongotp@example.com",
            "password": "password123"
        }
    )

    response = client.post(
        "/api/auth/signup/verify",
        json={
            "email": "wrongotp@example.com",
            "otp": "000000"
        }
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Incorrect OTP. Please try again."


def test_login_success(client, sent_otps):
    complete_signup(client, sent_otps)

    response = client.post(
        "/api/auth/login",
        json={
            "email": "test@example.com",
            "password": "password123"
        }
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Login verification OTP sent to your email."
    assert "huda_session" not in response.cookies

    verify_response = client.post(
        "/api/auth/login/verify",
        json={
            "email": "test@example.com",
            "otp": sent_otps[-1]["otp"]
        }
    )

    assert verify_response.status_code == 200
    assert verify_response.json()["message"] == "Login successful."
    assert "huda_session" in verify_response.cookies


def test_login_without_otp_does_not_create_session(client, sent_otps):
    complete_signup(client, sent_otps)

    response = client.post(
        "/api/auth/login",
        json={
            "email": "test@example.com",
            "password": "password123"
        }
    )

    assert response.status_code == 200

    me_response = client.get("/api/auth/me")

    assert me_response.status_code == 401


def test_login_wrong_password(client, sent_otps):
    complete_signup(client, sent_otps)

    response = client.post(
        "/api/auth/login",
        json={
            "email": "test@example.com",
            "password": "wrongpassword"
        }
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password."


def test_login_wrong_otp(client, sent_otps):
    complete_signup(client, sent_otps)

    client.post(
        "/api/auth/login",
        json={
            "email": "test@example.com",
            "password": "password123"
        }
    )

    response = client.post(
        "/api/auth/login/verify",
        json={
            "email": "test@example.com",
            "otp": "000000"
        }
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Incorrect OTP. Please try again."

    me_response = client.get("/api/auth/me")
    assert me_response.status_code == 401


def test_session_validation_after_login(client, sent_otps):
    create_logged_in_user(
        client,
        sent_otps,
        name="Session User",
        email="session@example.com"
    )

    response = client.get("/api/auth/me")

    assert response.status_code == 200
    assert response.json()["user"]["email"] == "session@example.com"


def test_logout(client, sent_otps):
    create_logged_in_user(
        client,
        sent_otps,
        name="Logout User",
        email="logout@example.com"
    )

    logout_response = client.post("/api/auth/logout")

    assert logout_response.status_code == 200
    assert logout_response.json()["message"] == "Logged out successfully."

    response = client.get("/api/auth/me")

    assert response.status_code == 401


def test_otp_resend(client, sent_otps):
    client.post(
        "/api/auth/signup",
        json={
            "name": "Resend User",
            "email": "resend@example.com",
            "password": "password123"
        }
    )

    # The first OTP request starts the 60-second cooldown.
    response = client.post(
        "/api/auth/otp/resend",
        json={
            "email": "resend@example.com",
            "purpose": "signup"
        }
    )

    assert response.status_code == 429
    assert response.json()["detail"] == "Please wait before requesting another OTP."


def test_otp_requires_six_digits(client, sent_otps):
    client.post(
        "/api/auth/signup",
        json={
            "name": "Test User",
            "email": "digits@example.com",
            "password": "password123"
        }
    )

    response = client.post(
        "/api/auth/signup/verify",
        json={
            "email": "digits@example.com",
            "otp": "123"
        }
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Please enter a valid 6-digit OTP."


# Conversation tests

def test_create_conversation_after_login(client, sent_otps):
    create_logged_in_user(client, sent_otps)

    response = client.post("/api/conversations")

    assert response.status_code == 200

    conversation = response.json()["conversation"]

    assert conversation["title"] == "New chat"
    assert conversation["id"]
    assert conversation["messages"] == []


def test_list_conversations_after_login(client, sent_otps):
    create_logged_in_user(client, sent_otps)

    client.post("/api/conversations")
    client.post("/api/conversations")

    response = client.get("/api/conversations")

    assert response.status_code == 200
    assert len(response.json()["conversations"]) == 2


def test_get_conversation_by_id(client, sent_otps):
    create_logged_in_user(client, sent_otps)

    create_response = client.post("/api/conversations")
    conversation_id = create_response.json()["conversation"]["id"]

    response = client.get(f"/api/conversations/{conversation_id}")

    assert response.status_code == 200
    assert response.json()["conversation"]["id"] == conversation_id
    assert response.json()["conversation"]["title"] == "New chat"


def test_get_conversation_invalid_id(client, sent_otps):
    create_logged_in_user(client, sent_otps)

    response = client.get("/api/conversations/invalid-id")

    assert response.status_code == 400


def test_rename_conversation(client, sent_otps):
    create_logged_in_user(client, sent_otps)

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


def test_rename_conversation_empty_title(client, sent_otps):
    create_logged_in_user(client, sent_otps)

    create_response = client.post("/api/conversations")
    conversation_id = create_response.json()["conversation"]["id"]

    response = client.patch(
        f"/api/conversations/{conversation_id}",
        json={"title": "   "}
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Title cannot be empty."


def test_rename_conversation_long_title(client, sent_otps):
    create_logged_in_user(client, sent_otps)

    create_response = client.post("/api/conversations")
    conversation_id = create_response.json()["conversation"]["id"]

    response = client.patch(
        f"/api/conversations/{conversation_id}",
        json={"title": "A" * 101}
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Title is too long."


def test_delete_conversation(client, sent_otps):
    create_logged_in_user(client, sent_otps)

    create_response = client.post("/api/conversations")
    conversation_id = create_response.json()["conversation"]["id"]

    response = client.delete(f"/api/conversations/{conversation_id}")

    assert response.status_code == 200
    assert response.json()["message"] == "Conversation deleted successfully."

    get_response = client.get(f"/api/conversations/{conversation_id}")

    assert get_response.status_code == 404


def test_user_cannot_access_another_users_conversation(client, sent_otps):
    create_logged_in_user(
        client,
        sent_otps,
        name="First User",
        email="first@example.com"
    )

    create_response = client.post("/api/conversations")
    conversation_id = create_response.json()["conversation"]["id"]

    client.post("/api/auth/logout")

    create_logged_in_user(
        client,
        sent_otps,
        name="Second User",
        email="second@example.com"
    )

    response = client.get(f"/api/conversations/{conversation_id}")

    assert response.status_code == 404




def test_startup_preserves_existing_production_index_names():
    import main as main_module

    def index_names(collection):
        return {kwargs.get("name") for _, kwargs in collection.index_calls}

    assert "email_1" in index_names(main_module.users_collection)
    assert "tokenHash_1" in index_names(main_module.sessions_collection)
    assert "expiresAt_1" in index_names(main_module.sessions_collection)

    # These are new collections/indexes introduced by the OTP feature.
    assert "unique_email_otp_purpose" in index_names(
        main_module.email_otps_collection
    )
    assert "ttl_otp_ip_limits" in index_names(
        main_module.otp_ip_limits_collection
    )

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

    assert response.status_code == 422

    error = response.json()["detail"][0]

    assert error["loc"] == ["body", "password"]
    assert error["type"] == "string_too_short"
    assert error["ctx"]["min_length"] == 8

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




def test_verified_login_otp_cannot_be_reused(client, sent_otps):
    complete_signup(client, sent_otps)

    client.post(
        "/api/auth/login",
        json={
            "email": "test@example.com",
            "password": "password123"
        }
    )
    otp = sent_otps[-1]["otp"]

    first_verification = client.post(
        "/api/auth/login/verify",
        json={"email": "test@example.com", "otp": otp}
    )
    assert first_verification.status_code == 200

    client.post("/api/auth/logout")

    reused_verification = client.post(
        "/api/auth/login/verify",
        json={"email": "test@example.com", "otp": otp}
    )
    assert reused_verification.status_code in (400, 429)
    assert client.get("/api/auth/me").status_code == 401


def test_otp_is_locked_after_five_incorrect_attempts(client, sent_otps):
    client.post(
        "/api/auth/signup",
        json={
            "name": "Locked User",
            "email": "locked@example.com",
            "password": "password123"
        }
    )
    correct_otp = sent_otps[-1]["otp"]

    for attempt in range(5):
        response = client.post(
            "/api/auth/signup/verify",
            json={
                "email": "locked@example.com",
                "otp": "000000" if correct_otp != "000000" else "111111"
            }
        )

        if attempt < 4:
            assert response.status_code == 400
        else:
            assert response.status_code == 429

    # Even the correct code must be rejected after the request is locked.
    locked_response = client.post(
        "/api/auth/signup/verify",
        json={"email": "locked@example.com", "otp": correct_otp}
    )
    assert locked_response.status_code == 429


def test_otp_hourly_request_limit(client, sent_otps):
    client.post(
        "/api/auth/signup",
        json={
            "name": "Rate Limit User",
            "email": "hourly-limit@example.com",
            "password": "password123"
        }
    )

    # Move the last-send timestamp outside the 60-second cooldown while
    # retaining a request count of five inside the current one-hour window.
    from datetime import datetime, timedelta, timezone
    import main as main_module

    otp_collection = main_module.email_otps_collection
    otp_record = otp_collection.find_one({
        "email": "hourly-limit@example.com",
        "purpose": "signup"
    })
    assert otp_record is not None

    now = datetime.now(timezone.utc)
    otp_collection.update_one(
        {"_id": otp_record["_id"]},
        {"$set": {
            "createdAt": now - timedelta(seconds=61),
            "requestWindowStartedAt": now - timedelta(minutes=10),
            "requestCount": 5
        }}
    )

    response = client.post(
        "/api/auth/otp/resend",
        json={
            "email": "hourly-limit@example.com",
            "purpose": "signup"
        }
    )

    assert response.status_code == 429
    assert response.json()["detail"] == (
        "Too many verification code requests. Please try again later."
    )


def test_password_reset_invalidates_existing_sessions(client, sent_otps):
    create_logged_in_user(
        client,
        sent_otps,
        name="Password Reset User",
        email="reset-session@example.com"
    )
    assert client.get("/api/auth/me").status_code == 200

    forgot_response = client.post(
        "/api/auth/forgot-password",
        json={"email": "reset-session@example.com"}
    )
    assert forgot_response.status_code == 200
    assert sent_otps[-1]["purpose"] == "password_reset"

    reset_response = client.post(
        "/api/auth/reset-password",
        json={
            "email": "reset-session@example.com",
            "otp": sent_otps[-1]["otp"],
            "new_password": "newpassword456"
        }
    )
    assert reset_response.status_code == 200

    # The cookie may still exist in the client, but its server-side session
    # must have been invalidated.
    assert client.get("/api/auth/me").status_code == 401




def test_password_reset_releases_otp_claim_when_password_update_fails(
    client, sent_otps, monkeypatch
):
    import main as main_module

    email = "reset-retry@example.com"
    create_logged_in_user(
        client,
        sent_otps,
        name="Password Reset Retry User",
        email=email
    )

    forgot_response = client.post(
        "/api/auth/forgot-password",
        json={"email": email}
    )
    assert forgot_response.status_code == 200
    otp = sent_otps[-1]["otp"]

    original_update_one = main_module.users_collection.update_one

    def fail_once(*args, **kwargs):
        # Restore the real method before raising so the retry can succeed.
        monkeypatch.setattr(
            main_module.users_collection,
            "update_one",
            original_update_one
        )
        raise RuntimeError("Simulated database update failure")

    monkeypatch.setattr(
        main_module.users_collection,
        "update_one",
        fail_once
    )

    failed_reset = client.post(
        "/api/auth/reset-password",
        json={
            "email": email,
            "otp": otp,
            "new_password": "newpassword456"
        }
    )

    assert failed_reset.status_code == 503

    # The same OTP should still be usable because the password update failed.
    retry_reset = client.post(
        "/api/auth/reset-password",
        json={
            "email": email,
            "otp": otp,
            "new_password": "newpassword456"
        }
    )

    assert retry_reset.status_code == 200


def test_signup_releases_otp_claim_when_account_insert_fails(client, sent_otps, monkeypatch):
    import main as main_module

    email = "signup-retry@example.com"
    signup_response = client.post(
        "/api/auth/signup",
        json={"name": "Signup Retry User", "email": email, "password": "password123"}
    )
    assert signup_response.status_code == 200
    otp = sent_otps[-1]["otp"]

    original_insert_one = main_module.users_collection.insert_one

    def fail_once(*args, **kwargs):
        monkeypatch.setattr(main_module.users_collection, "insert_one", original_insert_one)
        raise RuntimeError("Simulated temporary account insert failure")

    monkeypatch.setattr(main_module.users_collection, "insert_one", fail_once)

    failed_verification = client.post(
        "/api/auth/signup/verify",
        json={"email": email, "otp": otp}
    )
    assert failed_verification.status_code == 503
    assert main_module.users_collection.find_one({"email": email}) is None

    otp_record = main_module.email_otps_collection.find_one({"email": email, "purpose": "signup"})
    assert otp_record["consumedAt"] is None
    assert otp_record["signupInProgress"] is None

    retry_verification = client.post(
        "/api/auth/signup/verify",
        json={"email": email, "otp": otp}
    )
    assert retry_verification.status_code == 200
    assert retry_verification.json()["message"] == "Account created successfully."

    final_otp_record = main_module.email_otps_collection.find_one(
        {"email": email, "purpose": "signup"}
    )
    assert final_otp_record["consumedAt"] is not None
    assert final_otp_record["pendingUser"] is None
    assert final_otp_record["signupInProgress"] is None


def test_failed_email_delivery_does_not_mark_replacement_otp_as_failed(
    client, monkeypatch
):
    import main as main_module

    email = "delivery-race@example.com"

    def replace_then_fail(recipient, otp, purpose):
        current = main_module.email_otps_collection.find_one(
            {"email": email, "purpose": "signup"}
        )
        assert current is not None
        main_module.email_otps_collection.update_one(
            {"_id": current["_id"]},
            {"$set": {
                "createdAt": current["createdAt"] + __import__("datetime").timedelta(seconds=1),
                "otpHash": main_module.password_hash.hash("654321"),
                "deliveryFailedAt": None,
            }}
        )
        raise RuntimeError("Simulated email delivery failure after replacement")

    monkeypatch.setattr(main_module, "send_otp_email", replace_then_fail)

    response = client.post(
        "/api/auth/signup",
        json={"name": "Delivery Race User", "email": email, "password": "password123"}
    )
    assert response.status_code == 503

    replacement = main_module.email_otps_collection.find_one(
        {"email": email, "purpose": "signup"}
    )
    assert replacement is not None
    assert replacement["deliveryFailedAt"] is None


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



def test_otp_issuance_is_rate_limited_per_client_ip(client):
    # The per-IP limit is independent of email and purpose. Unknown emails
    # still receive the generic forgot-password response until the IP limit.
    for _ in range(20):
        response = client.post(
            "/api/auth/forgot-password",
            json={"email": "unknown@example.com"},
        )
        assert response.status_code == 200

    blocked = client.post(
        "/api/auth/forgot-password",
        json={"email": "another-unknown@example.com"},
    )
    assert blocked.status_code == 429
    assert "network" in blocked.json()["detail"].lower()


def test_ip_rate_limit_records_do_not_store_raw_ip(client):
    import main as main_module

    response = client.post(
        "/api/auth/forgot-password",
        json={"email": "unknown@example.com"},
    )
    assert response.status_code == 200

    records = list(main_module.otp_ip_limits_collection.find({}))
    assert len(records) == 1
    record = records[0]
    assert "ip" not in record
    assert "clientIp" not in record
    assert isinstance(record["_id"], str)


def test_profile_can_be_viewed_and_updated(client, sent_otps):
    create_logged_in_user(
        client,
        sent_otps,
        name="Before Update",
        email="profile@example.com",
    )

    profile = client.get("/api/auth/me")
    assert profile.status_code == 200
    assert profile.json()["user"]["name"] == "Before Update"

    updated = client.patch(
        "/api/auth/profile",
        json={"name": "After Update"},
    )
    assert updated.status_code == 200
    assert updated.json()["user"]["name"] == "After Update"

    refreshed = client.get("/api/auth/me")
    assert refreshed.status_code == 200
    assert refreshed.json()["user"]["name"] == "After Update"


def test_profile_update_requires_authentication(client):
    response = client.patch(
        "/api/auth/profile",
        json={"name": "Unauthorised Update"},
    )
    assert response.status_code == 401


def test_profile_name_has_maximum_length(client, sent_otps):
    create_logged_in_user(
        client,
        sent_otps,
        name="Profile User",
        email="profile-limit@example.com",
    )
    response = client.patch(
        "/api/auth/profile",
        json={"name": "x" * 81},
    )
    assert response.status_code == 422

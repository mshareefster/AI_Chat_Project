import base64
import io
import os
import json
from pathlib import Path
import hashlib
import hmac
import ipaddress
import secrets
from datetime import datetime, timedelta, timezone

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, Request, Response, Depends
from fastapi.middleware.cors import CORSMiddleware
from pypdf import PdfReader
from docx import Document
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError
from bson import ObjectId
from pydantic import BaseModel, EmailStr, Field
from pwdlib import PasswordHash

import smtplib
from email.message import EmailMessage
from email.utils import formataddr

load_dotenv()

API_BASE_URL = os.getenv("AI_API_BASE_URL", "").rstrip("/")
API_KEY = os.getenv("AI_API_KEY", "")
MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE_MB", "10")) * 1024 * 1024

MONGODB_URI = os.getenv("MONGODB_URI", "")
MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "huda_ai")

if not MONGODB_URI:
    print("WARNING: MONGODB_URI is not configured.")

mongo_client = MongoClient(MONGODB_URI)
db = mongo_client[MONGODB_DB_NAME]

password_hash = PasswordHash.recommended()

users_collection = db["users"]
sessions_collection = db["sessions"]
email_otps_collection = db["email_otps"]
otp_ip_limits_collection = db["otp_ip_limits"]

# Security indexes are mandatory when using real MongoDB. If index creation
# fails (for example, because duplicate legacy records exist), fail startup
# instead of silently running without the protections.
# Lightweight test doubles may omit create_index; real PyMongo collections
# always provide it.
if hasattr(users_collection, "create_index"):
    # Preserve the names of existing production indexes. MongoDB can report
    # IndexOptionsConflict when an equivalent index already exists under a
    # different name, even when its key pattern and options are identical.
    users_collection.create_index("email", unique=True, name="email_1")
    sessions_collection.create_index(
        "tokenHash", unique=True, name="tokenHash_1"
    )
    sessions_collection.create_index(
        "expiresAt", expireAfterSeconds=0, name="expiresAt_1"
    )
    email_otps_collection.create_index(
        [("email", 1), ("purpose", 1)],
        unique=True,
        name="unique_email_otp_purpose",
    )
    otp_ip_limits_collection.create_index(
        "expiresAt",
        expireAfterSeconds=0,
        name="ttl_otp_ip_limits",
    )

# OTP request throttling: 20 requests per source IP in each 15-minute window.
# Existing per-email limits remain in place as a second layer.
OTP_IP_WINDOW_SECONDS = 15 * 60
OTP_IP_MAX_REQUESTS = 20
TRUSTED_PROXY_IPS = {
    item.strip()
    for item in os.getenv("TRUSTED_PROXY_IPS", "127.0.0.1,::1").split(",")
    if item.strip()
}

SESSION_COOKIE_NAME = "huda_session"
SESSION_DAYS = 7

# =========================
# EMAIL OTP CONFIGURATION
# =========================

OTP_EXPIRY_MINUTES = 5
OTP_MAX_ATTEMPTS = 5
OTP_RESEND_SECONDS = 60


def get_client_ip(request: Request) -> str:
    """Return the peer IP, trusting X-Forwarded-For only from configured proxies."""
    peer_ip = request.client.host if request.client else "unknown"

    if peer_ip in TRUSTED_PROXY_IPS:
        forwarded_for = request.headers.get("x-forwarded-for", "")
        if forwarded_for:
            # Apache appends the address of its direct client. Use the last
            # entry; the first may have been supplied by an untrusted caller.
            candidate = forwarded_for.split(",")[-1].strip()
            try:
                return str(ipaddress.ip_address(candidate))
            except ValueError:
                pass

    return peer_ip


def enforce_otp_ip_rate_limit(request: Request):
    """Apply a fixed-window per-IP limit to all OTP issuance endpoints."""
    # The fake collection in unit tests has no create_index method and does
    # not emulate atomic upserts. Real MongoDB always has create_index.
    if not hasattr(otp_ip_limits_collection, "create_index"):
        return

    client_ip = get_client_ip(request)
    # HMAC prevents storing raw IP addresses or a directly guessable plain hash.
    hash_key = (MONGODB_URI or API_KEY or "local-development-only").encode("utf-8")
    ip_digest = hmac.new(hash_key, client_ip.encode("utf-8"), hashlib.sha256).hexdigest()

    now = datetime.now(timezone.utc)
    window_number = int(now.timestamp() // OTP_IP_WINDOW_SECONDS)
    bucket_id = f"{ip_digest}:{window_number}"
    expires_at = datetime.fromtimestamp(
        (window_number + 1) * OTP_IP_WINDOW_SECONDS + 86400,
        tz=timezone.utc,
    )

    limiter_filter = {"_id": bucket_id}
    limiter_update = {
        "$inc": {"requestCount": 1},
        "$setOnInsert": {"expiresAt": expires_at},
    }
    try:
        otp_ip_limits_collection.update_one(
            limiter_filter, limiter_update, upsert=True
        )
    except DuplicateKeyError:
        # Two first requests may race to create the same fixed-window bucket.
        # The unique _id lets one insert win; the other increments that record.
        otp_ip_limits_collection.update_one(
            limiter_filter,
            {"$inc": {"requestCount": 1}},
        )

    bucket = otp_ip_limits_collection.find_one(limiter_filter)
    if bucket and int(bucket.get("requestCount", 0)) > OTP_IP_MAX_REQUESTS:
        raise HTTPException(
            429,
            "Too many verification requests from this network. Please try again later.",
        )


def generate_otp():
    return f"{secrets.randbelow(1000000):06d}"


def send_otp_email(email: str, otp: str, purpose: str):
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_username = os.getenv("SMTP_USERNAME")
    smtp_password = os.getenv("SMTP_PASSWORD")
    from_email = os.getenv("SMTP_FROM_EMAIL")
    from_name = os.getenv("SMTP_FROM_NAME", "Huda AI")

    if not all([
        smtp_host,
        smtp_username,
        smtp_password,
        from_email,
    ]):
        raise RuntimeError("SMTP configuration is incomplete.")

    if purpose == "signup":
        subject = "Verify your Huda AI account"
    elif purpose == "password_reset":
        subject = "Reset your Huda AI password"
    else:
        subject = "Your Huda AI login verification code"

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = formataddr((from_name, from_email))
    message["To"] = email

    message.set_content(
        f"""Hello,

Your Huda AI verification code is:

{otp}

This code expires in {OTP_EXPIRY_MINUTES} minutes.

If you did not request this code, please ignore this email.

Regards,
Huda AI Team
"""
    )

    with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(smtp_username, smtp_password)
        server.send_message(message)

# =========================
# OTP STORAGE AND VERIFICATION
# =========================
def ensure_utc_aware(value):
    """
    Convert a datetime to timezone-aware UTC.
    MongoDB may return naive UTC datetimes.
    """
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)

def create_and_send_otp(email: str, purpose: str, pending_user=None):
    """Create or replace an OTP while retaining a persistent send-rate record.

    OTP documents are not deleted after successful verification. Keeping the
    record allows the resend cooldown and hourly request limit to survive OTP
    consumption. The consumedAt field prevents a code from being reused.
    """
    now = datetime.now(timezone.utc)
    key = {"email": email, "purpose": purpose}

    existing_otp = email_otps_collection.find_one(key)

    if existing_otp:
        if existing_otp.get("resetInProgress") is not None:
            raise HTTPException(
                429,
                "A password reset is already being processed. Please try again shortly."
            )
        if existing_otp.get("signupInProgress") is not None:
            raise HTTPException(
                429,
                "Account verification is already being processed. Please try again shortly."
            )

        last_sent = ensure_utc_aware(existing_otp["createdAt"])
        delivery_failed = bool(existing_otp.get("deliveryFailedAt"))

        if not delivery_failed and now < last_sent + timedelta(seconds=OTP_RESEND_SECONDS):
            raise HTTPException(
                429,
                "Please wait before requesting another OTP."
            )

        window_started = ensure_utc_aware(
            existing_otp.get("requestWindowStartedAt", existing_otp["createdAt"])
        )
        request_count = int(existing_otp.get("requestCount", 1))

        if now - window_started >= timedelta(hours=1):
            window_started = now
            request_count = 0

        if request_count >= 5:
            raise HTTPException(
                429,
                "Too many verification code requests. Please try again later."
            )

        next_count = request_count + 1
    else:
        window_started = now
        next_count = 1

    otp = generate_otp()
    otp_document = {
        **key,
        "otpHash": password_hash.hash(otp),
        "createdAt": now,
        "expiresAt": now + timedelta(minutes=OTP_EXPIRY_MINUTES),
        "attempts": 0,
        "pendingUser": pending_user,
        "consumedAt": None,
        "lockedAt": None,
        "deliveryFailedAt": None,
        "resetInProgress": None,
        "signupInProgress": None,
        "requestWindowStartedAt": window_started,
        "requestCount": next_count,
    }

    # Persist before sending so concurrent requests observe the cooldown.
    if existing_otp:
        otp_record_id = existing_otp["_id"]
        compare_filter = {
            "_id": existing_otp["_id"],
            "createdAt": existing_otp["createdAt"],
        }
        if "requestCount" in existing_otp:
            compare_filter["requestCount"] = existing_otp["requestCount"]
        compare_filter["resetInProgress"] = existing_otp.get("resetInProgress")
        compare_filter["signupInProgress"] = existing_otp.get("signupInProgress")

        result = email_otps_collection.update_one(
            compare_filter,
            {"$set": otp_document}
        )
        if getattr(result, "matched_count", 1) == 0:
            raise HTTPException(
                429,
                "A verification code was just requested. Please try again shortly."
            )
    else:
        try:
            insert_result = email_otps_collection.insert_one(otp_document)
            otp_record_id = insert_result.inserted_id
        except DuplicateKeyError:
            raise HTTPException(
                429,
                "A verification code was just requested. Please try again shortly."
            )

    try:
        send_otp_email(email, otp, purpose)
    except Exception:
        # Mark delivery failure only if this exact OTP is still current. A
        # concurrent resend may already have replaced it with a newer code.
        email_otps_collection.update_one(
            {
                "_id": otp_record_id,
                "createdAt": now,
                "otpHash": otp_document["otpHash"],
            },
            {"$set": {"deliveryFailedAt": datetime.now(timezone.utc)}}
        )
        raise HTTPException(
            503,
            "Unable to send verification email. Please try again later."
        )


def verify_otp(email: str, purpose: str, otp: str, consume: bool = True):
    """Verify an OTP; optionally defer consumption for a protected workflow."""
    key = {"email": email, "purpose": purpose}
    otp_document = email_otps_collection.find_one(key)

    if not otp_document:
        raise HTTPException(
            400,
            "OTP not found. Please request a new OTP."
        )

    if otp_document.get("consumedAt") is not None:
        raise HTTPException(400, "This OTP has already been used. Please request a new one.")

    if otp_document.get("lockedAt") is not None:
        raise HTTPException(429, "Too many incorrect attempts. Please request a new OTP.")

    if otp_document.get("resetInProgress") is not None or otp_document.get("signupInProgress") is not None:
        raise HTTPException(409, "This verification request is already being processed.")

    now = datetime.now(timezone.utc)
    expires_at = ensure_utc_aware(otp_document["expiresAt"])
    otp_identity = {
        "_id": otp_document["_id"],
        "createdAt": otp_document["createdAt"],
        "otpHash": otp_document["otpHash"],
    }

    if now >= expires_at:
        email_otps_collection.update_one(
            {**otp_identity, "consumedAt": None},
            {"$set": {"lockedAt": now}}
        )
        raise HTTPException(400, "OTP expired. Please request a new OTP.")

    attempts = int(otp_document.get("attempts", 0))
    if attempts >= OTP_MAX_ATTEMPTS:
        email_otps_collection.update_one(
            {**otp_identity, "consumedAt": None},
            {"$set": {"lockedAt": now}}
        )
        raise HTTPException(429, "Too many incorrect attempts. Please request a new OTP.")

    if not password_hash.verify(otp, otp_document["otpHash"]):
        new_attempts = attempts + 1
        update_fields = {"attempts": new_attempts}
        if new_attempts >= OTP_MAX_ATTEMPTS:
            update_fields["lockedAt"] = now

        # Compare-and-set prevents simultaneous incorrect attempts from
        # overwriting each other's attempt counter.
        result = email_otps_collection.update_one(
            {
                **otp_identity,
                "attempts": attempts,
                "consumedAt": None,
                "lockedAt": None,
            },
            {"$set": update_fields}
        )
        if getattr(result, "matched_count", 1) == 0:
            raise HTTPException(400, "OTP state changed. Please request a new OTP.")

        if new_attempts >= OTP_MAX_ATTEMPTS:
            raise HTTPException(429, "Too many incorrect attempts. Please request a new OTP.")
        raise HTTPException(400, "Incorrect OTP. Please try again.")

    # Password reset first verifies the code, then claims it while the
    # password and sessions are updated. Other OTP flows consume immediately.
    if not consume:
        return otp_document

    # This conditional update is the one-time-use gate. Only one concurrent
    # request can change consumedAt from None to a timestamp.
    result = email_otps_collection.update_one(
        {
            **otp_identity,
            "consumedAt": None,
            "lockedAt": None,
            "expiresAt": {"$gt": now},
        },
        {"$set": {"consumedAt": now}}
    )
    if getattr(result, "matched_count", 1) == 0:
        raise HTTPException(400, "This OTP has already been used. Please request a new one.")

    return otp_document

if not API_BASE_URL or not API_KEY:
    print("WARNING: AI_API_BASE_URL or AI_API_KEY is not configured.")

app = FastAPI(title="Huda AI Chat API")

# Keep the API same-origin in production. Add any additional trusted frontend
# origins through CORS_ORIGINS as a comma-separated environment variable.
CORS_ORIGINS = [
    origin.strip().rstrip("/")
    for origin in os.getenv(
        "CORS_ORIGINS",
        "https://chat.hudamusthafa.tech,http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

MODELS = [
    "claude-fable-5",
    "claude-fable-5-1",
    "claude-haiku-4-5-20251001",
    "claude-opus-5",
    "claude-opus-5-5",
    "claude-sonnet-5",
    "claude-sonnet-5-5",
    "deepseek/deepseek-V3.2",
    "deepseek/deepseek-v4-flash",
    "deepseek/deepseek-v4-pro",
    "google/gemini-3-flash-preview",
    "google/gemini-3.1-flash-lite",
    "google/gemini-3.1-pro-preview",
    "google/gemini-3.5-flash",
    "google/gemini-3.8-flash",
    "minimax/MiniMax-M2.5",
    "minimax/minimax-m3",
    "moonshot/kimi-k2.5",
    "moonshot/kimi-k3",
    "gpt-5.4",
    "gpt-5.4-mini",
    "gpt-5.5",
    "gpt-5.6-sol",
    "gpt-6-astra",
    "gpt-6-luna",
    "gpt-6-sol",
    "gpt-oss-120b",
    "qwen/qwen3.7-plus",
    "qwen/qwen3.8-flash",
    "typesafe/jev-1.13.0",
    "xai/grok-4.3",
    "xai/grok-4.7",
    "xiaomi/mimo-v2.6-flash",
    "xiaomi/mimo-v2.6-pro",
    "zai/glm-5.1",
    "zai/glm-5.3-flash",
]

TEXT_EXTENSIONS = {
    ".txt", ".md", ".csv", ".json", ".js", ".jsx", ".ts", ".tsx",
    ".html", ".css", ".py", ".java", ".c", ".cpp", ".sql", ".xml",
    ".yaml", ".yml", ".env", ".log"
}
IMAGE_TYPES = {"image/png", "image/jpeg", "image/webp", "image/gif"}

def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_session(user_id):
    token = secrets.token_urlsafe(32)

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=SESSION_DAYS)

    sessions_collection.insert_one({
        "tokenHash": hash_session_token(token),
        "userId": user_id,
        "createdAt": now,
        "expiresAt": expires_at,
    })

    return token

async def get_current_user(request: Request):
    token = request.cookies.get(SESSION_COOKIE_NAME)

    if not token:
        raise HTTPException(401, "Not authenticated.")

    session = sessions_collection.find_one({
        "tokenHash": hash_session_token(token),
        "expiresAt": {"$gt": datetime.now(timezone.utc)}
    })

    if not session:
        raise HTTPException(401, "Session expired.")

    user = users_collection.find_one({
        "_id": session["userId"]
    })

    if not user:
        raise HTTPException(401, "User not found.")

    # Password reset invalidates every session created before the password
    # update, even if physical session cleanup is temporarily unavailable.
    password_updated_at = user.get("passwordUpdatedAt")
    session_created_at = session.get("createdAt")
    if password_updated_at is not None:
        if session_created_at is None or (
            ensure_utc_aware(session_created_at)
            < ensure_utc_aware(password_updated_at)
        ):
            raise HTTPException(401, "Session expired. Please sign in again.")

    return user
class SignupRequest(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)

class OTPVerificationRequest(BaseModel):
    email: EmailStr
    otp: str

class OTPResendRequest(BaseModel):
    email: EmailStr
    purpose: str


class EmailRequest(BaseModel):
    email: EmailStr


class PasswordResetRequest(BaseModel):
    email: EmailStr
    otp: str
    new_password: str = Field(min_length=8, max_length=128)


class UpdateProfileRequest(BaseModel):
    name: str = Field(min_length=2, max_length=80)

@app.post("/api/auth/signup")
async def signup(data: SignupRequest, request: Request):
    enforce_otp_ip_rate_limit(request)
    name = data.name.strip()
    email = str(data.email).lower().strip()

    if len(name) < 2:
        raise HTTPException(400, "Name must be at least 2 characters.")

    if len(data.password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters.")

    existing_user = users_collection.find_one({"email": email})

    if existing_user:
        raise HTTPException(
            409,
            "An account with this email already exists."
        )

    pending_user = {
        "name": name,
        "email": email,
        "passwordHash": password_hash.hash(data.password),
        "authProvider": "local",
    }

    create_and_send_otp(
        email=email,
        purpose="signup",
        pending_user=pending_user
    )

    return {
        "message": "Verification OTP sent to your email.",
        "email": email,
    }


@app.post("/api/auth/signup/verify")
async def verify_signup(data: OTPVerificationRequest):
    email = str(data.email).lower().strip()

    if len(data.otp) != 6 or not data.otp.isdigit():
        raise HTTPException(400, "Please enter a valid 6-digit OTP.")

    # Validate first without consuming. The conditional claim below protects
    # this exact OTP while the account insert is attempted.
    otp_document = verify_otp(email, "signup", data.otp, consume=False)
    pending_user = otp_document.get("pendingUser")

    if not pending_user:
        raise HTTPException(
            400,
            "Registration details not found. Please sign up again."
        )

    if users_collection.find_one({"email": email}):
        raise HTTPException(
            409,
            "An account with this email already exists."
        )

    now = datetime.now(timezone.utc)
    signup_claim = secrets.token_urlsafe(24)
    claim_result = email_otps_collection.update_one(
        {
            "_id": otp_document["_id"],
            "createdAt": otp_document["createdAt"],
            "otpHash": otp_document["otpHash"],
            "expiresAt": {"$gt": now},
            "consumedAt": None,
            "lockedAt": None,
            "resetInProgress": None,
            "signupInProgress": None,
        },
        {"$set": {"signupInProgress": signup_claim}}
    )
    if getattr(claim_result, "matched_count", 1) == 0:
        raise HTTPException(
            409,
            "This account verification is already being processed. Please try again."
        )

    pending_user["emailVerified"] = True
    pending_user["createdAt"] = now

    try:
        result = users_collection.insert_one(pending_user)
    except DuplicateKeyError:
        # Another request may have created the account after our initial read.
        # Consume this OTP and clear the retained registration payload.
        email_otps_collection.update_one(
            {"_id": otp_document["_id"], "signupInProgress": signup_claim},
            {"$set": {
                "consumedAt": datetime.now(timezone.utc),
                "pendingUser": None,
                "signupInProgress": None,
            }}
        )
        raise HTTPException(409, "An account with this email already exists.")
    except Exception as exc:
        # Account insertion did not complete. Release the claim so the user can
        # retry with the same unexpired OTP instead of requesting another one.
        try:
            release_result = email_otps_collection.update_one(
                {"_id": otp_document["_id"], "signupInProgress": signup_claim},
                {"$set": {"signupInProgress": None}}
            )
            if getattr(release_result, "matched_count", 1) == 0:
                print("WARNING: Signup failed and OTP claim could not be released.")
        except Exception as release_exc:
            print(
                "WARNING: Signup failed and OTP claim release failed: "
                f"{type(release_exc).__name__}"
            )
        print(f"WARNING: Signup account insertion failed: {type(exc).__name__}")
        raise HTTPException(
            503,
            "Unable to create your account right now. Please try again."
        )

    # Account creation succeeded. Consume the OTP and remove the pending
    # password hash from its document. If finalization fails, retain the claim
    # so this OTP cannot be replayed against the newly created account.
    try:
        finalize_result = email_otps_collection.update_one(
            {"_id": otp_document["_id"], "signupInProgress": signup_claim},
            {"$set": {
                "consumedAt": datetime.now(timezone.utc),
                "pendingUser": None,
                "signupInProgress": None,
            }}
        )
        if getattr(finalize_result, "matched_count", 1) == 0:
            print("WARNING: Signup succeeded but OTP finalization did not match the active claim.")
    except Exception as exc:
        print(f"WARNING: Signup succeeded but OTP finalization failed: {type(exc).__name__}")

    return {
        "message": "Account created successfully.",
        "user": {
            "id": str(result.inserted_id),
            "name": pending_user["name"],
            "email": email,
        },
    }


@app.post("/api/auth/forgot-password")
async def forgot_password(data: EmailRequest, request: Request):
    enforce_otp_ip_rate_limit(request)
    email = str(data.email).lower().strip()

    user = users_collection.find_one({"email": email})

    # Use the same response for existing and non-existing accounts.
    # This avoids disclosing whether an email is registered.
    if user and user.get("authProvider") == "local":
        try:
            create_and_send_otp(
                email=email,
                purpose="password_reset"
            )
        except Exception as exc:
            # Keep the response identical for known and unknown email
            # addresses. Log only the exception type, never email/OTP details.
            print(f"WARNING: Forgot-password OTP delivery/request failed: {type(exc).__name__}")

    return {
        "message": "If a matching account exists, a password reset code will be sent."
    }


@app.post("/api/auth/reset-password")
async def reset_password(data: PasswordResetRequest):
    email = str(data.email).lower().strip()

    if len(data.otp) != 6 or not data.otp.isdigit():
        raise HTTPException(400, "Please enter a valid 6-digit OTP.")

    if len(data.new_password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters.")

    # Prepare the expensive password hash before claiming the OTP.
    new_password_hash = password_hash.hash(data.new_password)

    otp_document = verify_otp(
        email,
        "password_reset",
        data.otp,
        consume=False
    )

    user = users_collection.find_one({"email": email})
    if not user or user.get("authProvider") != "local":
        raise HTTPException(
            400,
            "Unable to reset password. Please request a new code."
        )

    # Claim the OTP atomically. Only one reset request can proceed with it.
    # If a later database operation fails, the claim is released so the user
    # can retry with the same still-valid OTP.
    reset_claim = secrets.token_urlsafe(24)
    claim_result = email_otps_collection.update_one(
        {
            "_id": otp_document["_id"],
            "createdAt": otp_document["createdAt"],
            "otpHash": otp_document["otpHash"],
            "expiresAt": {"$gt": datetime.now(timezone.utc)},
            "consumedAt": None,
            "lockedAt": None,
            "resetInProgress": None,
        },
        {"$set": {"resetInProgress": reset_claim}}
    )
    if getattr(claim_result, "matched_count", 1) == 0:
        raise HTTPException(
            409,
            "This password reset request is already being processed. Please try again."
        )

    try:
        # Update the password first. get_current_user() rejects sessions
        # created before passwordUpdatedAt, so all old sessions are logically
        # revoked as soon as this single-document user update succeeds.
        update_result = users_collection.update_one(
            {"_id": user["_id"], "authProvider": "local"},
            {
                "$set": {
                    "passwordHash": new_password_hash,
                    "passwordUpdatedAt": datetime.now(timezone.utc)
                }
            }
        )
        if getattr(update_result, "matched_count", 1) == 0:
            email_otps_collection.update_one(
                {"_id": otp_document["_id"], "resetInProgress": reset_claim},
                {"$set": {"resetInProgress": None}}
            )
            raise HTTPException(404, "Account not found. Please try again.")

        # Physical cleanup is best-effort. Even if MongoDB cannot delete these
        # records, the passwordUpdatedAt check makes the old sessions unusable.
        try:
            sessions_collection.delete_many({"userId": user["_id"]})
        except Exception as cleanup_exc:
            print(
                "WARNING: Password reset succeeded but old session cleanup failed: "
                f"{type(cleanup_exc).__name__}"
            )

    except HTTPException:
        raise
    except Exception as exc:
        # Password update did not complete. Release the claim so the user can
        # retry with the same still-valid OTP. If release fails, fail closed.
        try:
            release_result = email_otps_collection.update_one(
                {"_id": otp_document["_id"], "resetInProgress": reset_claim},
                {"$set": {"resetInProgress": None}}
            )
            if getattr(release_result, "matched_count", 1) == 0:
                print("WARNING: Password reset failed and OTP claim could not be released.")
        except Exception as release_exc:
            print(
                "WARNING: Password reset failed and OTP claim release failed: "
                f"{type(release_exc).__name__}"
            )

        print(f"WARNING: Password reset database operation failed: {type(exc).__name__}")
        raise HTTPException(
            503,
            "Unable to complete the password reset. Please try again."
        )

    # The password is now changed and old sessions have been revoked.
    # Consume the OTP. If this final bookkeeping write fails, keep the claim
    # in place (fail closed) so the same OTP cannot be used again.
    try:
        finalize_result = email_otps_collection.update_one(
            {"_id": otp_document["_id"], "resetInProgress": reset_claim},
            {
                "$set": {
                    "consumedAt": datetime.now(timezone.utc),
                    "resetInProgress": None,
                }
            }
        )
        if getattr(finalize_result, "matched_count", 1) == 0:
            print(
                "WARNING: Password reset succeeded but OTP finalization "
                "did not match the active reset claim."
            )
    except Exception as exc:
        print(
            "WARNING: Password reset succeeded but OTP finalization failed: "
            f"{type(exc).__name__}"
        )

    return {
        "message": "Password reset successfully. Please sign in again."
    }


@app.post("/api/auth/login")
async def login(data: LoginRequest, request: Request):
    enforce_otp_ip_rate_limit(request)
    email = str(data.email).lower().strip()

    user = users_collection.find_one({"email": email})

    if not user:
        raise HTTPException(401, "Invalid email or password.")

    if user.get("authProvider") != "local":
        raise HTTPException(
            400,
            "This account uses Google Sign-In. Please continue with Google."
        )

    if not password_hash.verify(data.password, user["passwordHash"]):
        raise HTTPException(401, "Invalid email or password.")

    create_and_send_otp(
        email=email,
        purpose="login"
    )

    return {
        "message": "Login verification OTP sent to your email.",
        "email": email,
    }


@app.post("/api/auth/login/verify")
async def verify_login(data: OTPVerificationRequest, response: Response):
    email = str(data.email).lower().strip()

    if len(data.otp) != 6 or not data.otp.isdigit():
        raise HTTPException(400, "Please enter a valid 6-digit OTP.")

    verify_otp(email, "login", data.otp)

    user = users_collection.find_one({"email": email})

    if not user or user.get("authProvider") != "local":
        raise HTTPException(401, "Unable to verify login.")

    # Verify existing accounts that were created before OTP was introduced.
    users_collection.update_one(
        {"_id": user["_id"]},
        {"$set": {"emailVerified": True}}
    )

    token = create_session(user["_id"])

    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=SESSION_DAYS * 24 * 60 * 60,
        path="/",
    )

    return {
        "message": "Login successful.",
        "user": {
            "id": str(user["_id"]),
            "name": user["name"],
            "email": email,
        },
    }


@app.post("/api/auth/otp/resend")
async def resend_otp(data: OTPResendRequest, request: Request):
    enforce_otp_ip_rate_limit(request)
    email = str(data.email).lower().strip()
    purpose = data.purpose.strip().lower()

    if purpose not in {"signup", "login", "password_reset"}:
        raise HTTPException(400, "Invalid OTP purpose.")

    existing_otp = email_otps_collection.find_one({
        "email": email,
        "purpose": purpose
    })

    if purpose == "password_reset":
        user = users_collection.find_one({"email": email})
        if user and user.get("authProvider") == "local" and existing_otp:
            try:
                create_and_send_otp(email=email, purpose="password_reset")
            except HTTPException:
                pass
        return {
            "message": "If a matching account and pending reset request exist, a new code will be sent."
        }

    if not existing_otp:
        raise HTTPException(
            404,
            "No pending verification found. Please start again."
        )

    if purpose == "signup":
        if users_collection.find_one({"email": email}):
            raise HTTPException(
                409,
                "An account with this email already exists."
            )

        pending_user = existing_otp.get("pendingUser")

        if not pending_user:
            raise HTTPException(
                400,
                "Registration details not found. Please sign up again."
            )

        create_and_send_otp(
            email=email,
            purpose="signup",
            pending_user=pending_user
        )

    else:
        user = users_collection.find_one({"email": email})

        if not user or user.get("authProvider") != "local":
            raise HTTPException(
                404,
                "Account not found. Please start again."
            )

        create_and_send_otp(
            email=email,
            purpose="login"
        )

    return {
        "message": "A new verification OTP has been sent."
    }

@app.get("/api/auth/me")
async def auth_me(current_user: dict = Depends(get_current_user)):
    return {
        "user": {
            "id": str(current_user["_id"]),
            "name": current_user["name"],
            "email": current_user["email"],
        }
    }

@app.patch("/api/auth/profile")
async def update_profile(
    data: UpdateProfileRequest,
    current_user: dict = Depends(get_current_user)
):
    name = data.name.strip()

    if len(name) < 2:
        raise HTTPException(400, "Name must be at least 2 characters.")

    update_result = users_collection.update_one(
        {"_id": current_user["_id"]},
        {"$set": {"name": name, "updatedAt": datetime.now(timezone.utc)}}
    )
    if getattr(update_result, "matched_count", 1) == 0:
        raise HTTPException(404, "User account not found.")

    return {
        "message": "Profile updated successfully.",
        "user": {
            "id": str(current_user["_id"]),
            "name": name,
            "email": current_user["email"]
        }
    }


@app.post("/api/auth/logout")
async def logout(request: Request, response: Response):
    token = request.cookies.get(SESSION_COOKIE_NAME)

    if token:
        sessions_collection.delete_one({
            "tokenHash": hash_session_token(token)
        })

    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/"
    )

    return {"message": "Logged out successfully."}


@app.get("/api/health")
async def health():
    return {"status": "ok"}

@app.get("/api/db-test")
async def db_test():
    try:
        mongo_client.admin.command("ping")
        return {"status": "ok", "database": MONGODB_DB_NAME}
    except Exception as exc:
        raise HTTPException(500, f"MongoDB connection failed: {exc}")

@app.get("/api/models")
async def models():
    return {"models": MODELS}
@app.post("/api/conversations")
async def create_conversation(
    current_user: dict = Depends(get_current_user)
):
    now = datetime.now(timezone.utc)

    conversation = {
        "userId": current_user["_id"],
        "title": "New chat",
        "model": MODELS[0],
        "messages": [],
        "createdAt": now,
        "updatedAt": now,
    }

    result = db["conversations"].insert_one(conversation)

    return {
        "conversation": {
            "id": str(result.inserted_id),
            "title": conversation["title"],
            "model": conversation["model"],
            "messages": [],
            "createdAt": now.isoformat(),
            "updatedAt": now.isoformat(),
        }
    }


@app.get("/api/conversations")
async def list_conversations(
    current_user: dict = Depends(get_current_user)
):
    conversations = db["conversations"].find(
        {
            "userId": current_user["_id"]
        }
    ).sort(
        "updatedAt",
        -1
    )

    result = []

    for conversation in conversations:
        result.append({
            "id": str(conversation["_id"]),
            "title": conversation.get("title", "New chat"),
            "model": conversation.get("model"),
            "createdAt": conversation["createdAt"].isoformat(),
            "updatedAt": conversation["updatedAt"].isoformat(),
        })

    return {
        "conversations": result
    }


@app.get("/api/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    current_user: dict = Depends(get_current_user)
):
    if not ObjectId.is_valid(conversation_id):
        raise HTTPException(400, "Invalid conversation ID.")

    conversation = db["conversations"].find_one({
        "_id": ObjectId(conversation_id),
        "userId": current_user["_id"]
    })

    if not conversation:
        raise HTTPException(404, "Conversation not found.")

    return {
        "conversation": {
            "id": str(conversation["_id"]),
            "title": conversation.get("title", "New chat"),
            "model": conversation.get("model"),
            "messages": conversation.get("messages", []),
            "createdAt": conversation["createdAt"].isoformat(),
            "updatedAt": conversation["updatedAt"].isoformat(),
        }
    }


class RenameConversationRequest(BaseModel):
    title: str


@app.patch("/api/conversations/{conversation_id}")
async def rename_conversation(
    conversation_id: str,
    data: RenameConversationRequest,
    current_user: dict = Depends(get_current_user)
):
    if not ObjectId.is_valid(conversation_id):
        raise HTTPException(400, "Invalid conversation ID.")

    title = data.title.strip()

    if not title:
        raise HTTPException(400, "Title cannot be empty.")

    if len(title) > 100:
        raise HTTPException(400, "Title is too long.")

    result = db["conversations"].update_one(
        {
            "_id": ObjectId(conversation_id),
            "userId": current_user["_id"]
        },
        {
            "$set": {
                "title": title,
                "updatedAt": datetime.now(timezone.utc)
            }
        }
    )

    if result.matched_count == 0:
        raise HTTPException(404, "Conversation not found.")

    return {
        "message": "Conversation renamed successfully."
    }


@app.delete("/api/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    current_user: dict = Depends(get_current_user)
):
    if not ObjectId.is_valid(conversation_id):
        raise HTTPException(400, "Invalid conversation ID.")

    result = db["conversations"].delete_one({
        "_id": ObjectId(conversation_id),
        "userId": current_user["_id"]
    })

    if result.deleted_count == 0:
        raise HTTPException(404, "Conversation not found.")

    return {
        "message": "Conversation deleted successfully."
    }

def data_url(content: bytes, content_type: str) -> str:
    encoded = base64.b64encode(content).decode("utf-8")
    return f"data:{content_type};base64,{encoded}"

async def file_to_content(upload: UploadFile):
    data = await upload.read()
    if len(data) > MAX_FILE_SIZE:
        raise HTTPException(413, f"{upload.filename} is larger than the allowed limit.")

    content_type = upload.content_type or "application/octet-stream"
    suffix = Path(upload.filename or "").suffix.lower()

    if content_type in IMAGE_TYPES:
        return {
            "type": "image_url",
            "image_url": {"url": data_url(data, content_type)}
        }

    try:
        if suffix == ".pdf" or content_type == "application/pdf":
            reader = PdfReader(io.BytesIO(data))
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
            return {"type": "text", "text": f"\n\n[Attached PDF: {upload.filename}]\n{text[:120000]}"}

        if suffix == ".docx":
            doc = Document(io.BytesIO(data))
            text = "\n".join(p.text for p in doc.paragraphs)
            return {"type": "text", "text": f"\n\n[Attached DOCX: {upload.filename}]\n{text[:120000]}"}

        if suffix in TEXT_EXTENSIONS or content_type.startswith("text/"):
            text = data.decode("utf-8", errors="replace")
            return {"type": "text", "text": f"\n\n[Attached file: {upload.filename}]\n{text[:120000]}"}

    except Exception as exc:
        raise HTTPException(400, f"Could not read {upload.filename}: {exc}")

    return {
        "type": "text",
        "text": f"\n\n[Attached file: {upload.filename}. Binary files are not text-extracted by this version.]"
    }

@app.post("/api/chat")
async def chat(
    conversationId: str = Form(...),
    model: str = Form(...),
    message: str = Form(""),
    files: list[UploadFile] = File(default=[]),
    current_user: dict = Depends(get_current_user),
):
    if model not in MODELS:
        raise HTTPException(400, "Invalid model selected.")

    if not API_BASE_URL or not API_KEY:
        raise HTTPException(500, "AI API is not configured on the server.")

    if not ObjectId.is_valid(conversationId):
        raise HTTPException(400, "Invalid conversation ID.")

    conversation = db["conversations"].find_one({
        "_id": ObjectId(conversationId),
        "userId": current_user["_id"]
    })

    if not conversation:
        raise HTTPException(404, "Conversation not found.")

    parts = []

    if message.strip():
        parts.append({
            "type": "text",
            "text": message
        })

    for upload in files:
        parts.append(await file_to_content(upload))

    if not parts:
        raise HTTPException(
            400,
            "Please enter a message or attach a file/image."
        )

    old_messages = conversation.get("messages", [])

    messages = []

    for item in old_messages[-20:]:
        if isinstance(item, dict) and item.get("role") in {"user", "assistant"}:
            messages.append({
                "role": item["role"],
                "content": item.get("content", "")
            })

    messages.append({
        "role": "user",
        "content": parts
    })

    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
    }

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

    endpoint = API_BASE_URL + "/chat/completions"

    try:
        async with httpx.AsyncClient(timeout=180) as client:
            response = await client.post(
                endpoint,
                json=payload,
                headers=headers
            )

        if response.status_code >= 400:
            detail = response.text[:4000]
            raise HTTPException(
                response.status_code,
                f"Upstream AI error: {detail}"
            )

        result = response.json()

        choices = result.get("choices", [])

        if not choices:
            raise HTTPException(
                502,
                "The AI provider returned no choices."
            )

        content = choices[0].get("message", {}).get("content", "")

        now = datetime.now(timezone.utc)

        user_message = {
            "role": "user",
            "content": message,
            "createdAt": now,
        }

        assistant_message = {
            "role": "assistant",
            "content": content,
            "createdAt": now,
            "model": model,
        }

        
        conversation_update = {
            "$push": {
                "messages": {
                    "$each": [
                        user_message,
                        assistant_message
                    ]
                }
            },
            "$set": {
                "model": model,
                "updatedAt": now
            }
        }

        # Set a title from the first user message
        if conversation.get("title") == "New chat":
            if message.strip():
                title = " ".join(message.strip().split())

                if len(title) > 50:
                    title = title[:50].rstrip() + "..."

                conversation_update["$set"]["title"] = title

            elif files:
                conversation_update["$set"]["title"] = (
                    f"Chat with {len(files)} attachment(s)"
                )

        db["conversations"].update_one(
            {
                "_id": ObjectId(conversationId),
                "userId": current_user["_id"]
            },
            conversation_update
        )


        return {
            "conversationId": conversationId,
            "model": model,
            "content": content,
        }

    except httpx.RequestError as exc:
        raise HTTPException(
            502,
            f"Could not connect to AI provider: {exc}"
        )

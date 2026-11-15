import base64
import io
import os
import json
from pathlib import Path
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, Request, Response, Depends
from fastapi.middleware.cors import CORSMiddleware
from pypdf import PdfReader
from docx import Document
from pymongo import MongoClient
from bson import ObjectId
from pydantic import BaseModel, EmailStr
from pwdlib import PasswordHash

load_dotenv()

API_BASE_URL = os.getenv("AI_API_BASE_URL", "").rstrip("/")
API_KEY = os.getenv("AI_API_KEY", "")
MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE_MB", "10")) * 1024 * 1024

MONGODB_URI = os.getenv("MONGODB_URI", "")

if not MONGODB_URI:
    print("WARNING: MONGODB_URI is not configured.")

mongo_client = MongoClient(MONGODB_URI)
db = mongo_client["huda_ai"]

password_hash = PasswordHash.recommended()

users_collection = db["users"]
sessions_collection = db["sessions"]

SESSION_COOKIE_NAME = "huda_session"
SESSION_DAYS = 7

if not API_BASE_URL or not API_KEY:
    print("WARNING: AI_API_BASE_URL or AI_API_KEY is not configured.")

app = FastAPI(title="Huda AI Chat API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict this to https://chat.hudamusthafa.tech later.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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

    return user
class SignupRequest(BaseModel):
    name: str
    email: EmailStr
    password: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

@app.post("/api/auth/signup")
async def signup(data: SignupRequest):
    name = data.name.strip()
    email = data.email.lower().strip()

    if len(name) < 2:
        raise HTTPException(400, "Name must be at least 2 characters.")

    if len(data.password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters.")

    existing_user = users_collection.find_one({"email": email})

    if existing_user:
        raise HTTPException(409, "An account with this email already exists.")

    hashed_password = password_hash.hash(data.password)

    user = {
        "name": name,
        "email": email,
        "passwordHash": hashed_password,
        "authProvider": "local",
        "createdAt": datetime.now(timezone.utc),
    }

    result = users_collection.insert_one(user)

    return {
        "message": "Account created successfully.",
        "user": {
            "id": str(result.inserted_id),
            "name": name,
            "email": email,
        },
    }

@app.post("/api/auth/login")
async def login(data: LoginRequest, response: Response):
    email = data.email.lower().strip()

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
            "email": user["email"],
        },
    }

@app.get("/api/auth/me")
async def auth_me(request: Request):
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

    return {
        "user": {
            "id": str(user["_id"]),
            "name": user["name"],
            "email": user["email"],
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
        return {"status": "ok", "database": "huda_ai"}
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


import os
import sys
from pathlib import Path
from copy import deepcopy

import pymongo
import pytest


# Test-only configuration. Never use production credentials.
os.environ["MONGODB_URI"] = "mongodb://127.0.0.1:27017/"
os.environ["AI_API_BASE_URL"] = "https://example.invalid/v1"
os.environ["AI_API_KEY"] = "test-only-dummy-key"

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))


class FakeInsertResult:
    def __init__(self, inserted_id):
        self.inserted_id = inserted_id


class FakeUpdateResult:
    def __init__(self, matched_count):
        self.matched_count = matched_count


class FakeDeleteResult:
    def __init__(self, deleted_count):
        self.deleted_count = deleted_count


class FakeCursor:
    def __init__(self, documents):
        self.documents = documents

    def sort(self, field, direction):
        self.documents.sort(
            key=lambda document: document.get(field),
            reverse=direction == -1
        )
        return self

    def __iter__(self):
        return iter(deepcopy(self.documents))


class FakeCollection:
    def __init__(self):
        self.documents = []

    def matches(self, document, query):
        for key, expected in query.items():
            actual = document.get(key)

            if isinstance(expected, dict):
                if "$gt" in expected:
                    if actual is None or not actual > expected["$gt"]:
                        return False
                else:
                    return False
            elif actual != expected:
                return False

        return True

    def find_one(self, query):
        for document in self.documents:
            if self.matches(document, query):
                return deepcopy(document)
        return None

    def find(self, query):
        matched = [
            document for document in self.documents
            if self.matches(document, query)
        ]
        return FakeCursor(matched)

    def insert_one(self, document):
        from bson import ObjectId

        new_document = deepcopy(document)
        new_document["_id"] = ObjectId()
        self.documents.append(new_document)

        return FakeInsertResult(new_document["_id"])

    def update_one(self, query, update):
        for document in self.documents:
            if self.matches(document, query):
                if "$set" in update:
                    document.update(deepcopy(update["$set"]))

                return FakeUpdateResult(1)

        return FakeUpdateResult(0)

    def delete_one(self, query):
        for index, document in enumerate(self.documents):
            if self.matches(document, query):
                self.documents.pop(index)
                return FakeDeleteResult(1)

        return FakeDeleteResult(0)


class FakeDatabase:
    def __init__(self):
        self.collections = {}

    def __getitem__(self, name):
        if name not in self.collections:
            self.collections[name] = FakeCollection()
        return self.collections[name]


class FakeMongoClient:
    def __init__(self, *args, **kwargs):
        self.databases = {}

    def __getitem__(self, name):
        if name not in self.databases:
            self.databases[name] = FakeDatabase()
        return self.databases[name]


pymongo.MongoClient = FakeMongoClient

from fastapi.testclient import TestClient
import main as main_module
from main import app, users_collection, sessions_collection, db

@pytest.fixture
def sent_otps(monkeypatch):
    captured_otps = []

    def fake_send_otp_email(email, otp, purpose):
        captured_otps.append({
            "email": email,
            "otp": otp,
            "purpose": purpose,
        })

    monkeypatch.setattr(
        main_module,
        "send_otp_email",
        fake_send_otp_email
    )

    return captured_otps

@pytest.fixture
def client(sent_otps):
    users_collection.documents.clear()
    sessions_collection.documents.clear()
    db["conversations"].documents.clear()
    email_otps_collection = db["email_otps"]
    email_otps_collection.documents.clear()
    
    with TestClient(
        app,
        base_url="https://testserver"
    ) as test_client:
        yield test_client


import asyncio
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

import sys
import types
from pathlib import Path
import os
sys.modules.setdefault("uiautomator2", types.ModuleType("uiautomator2"))
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault("API_KEY", "testkey")

import api


class DummyJobManager:
    def __init__(self, job_data=None):
        self.job_data = job_data or {}

    def new_job(self):
        return "job123"

    def ensure_no_running(self):
        pass

    def get_job(self, job_id):
        return self.job_data.get(job_id)

    def complete_job(self, job_id, results):
        self.job_data[job_id] = {
            "status": "completed",
            "results": results,
            "error": None,
            "created_at": datetime.utcnow(),
        }

    def fail_job(self, job_id, error):
        self.job_data[job_id] = {
            "status": "failed",
            "results": None,
            "error": error,
            "created_at": datetime.utcnow(),
        }


def test_submit_check(monkeypatch):
    monkeypatch.setattr(api, "job_manager", DummyJobManager())
    monkeypatch.setattr(api, "_new_job", lambda: "job123")
    called = {}

    def fake_add_task(fn, *args):
        called["task"] = (fn, args)

    client = TestClient(api.app)
    response = client.post(
        "/check_numbers",
        json={"numbers": ["123"], "service": "getcontact"},
        headers={"X-API-Key": api.settings.api_key},
    )
    assert response.status_code == 200
    assert response.json() == {"job_id": "job123"}


def test_get_status(monkeypatch):
    results = [api.CheckResult(phone_number="123", status="Ok", details="")]
    job_data = {
        "job123": {
            "status": "completed",
            "results": results,
            "error": None,
            "created_at": datetime.utcnow(),
        }
    }
    monkeypatch.setattr(api, "job_manager", DummyJobManager(job_data))

    client = TestClient(api.app)
    response = client.get(
        "/status/job123",
        headers={"X-API-Key": api.settings.api_key},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["results"][0]["phone_number"] == "123"


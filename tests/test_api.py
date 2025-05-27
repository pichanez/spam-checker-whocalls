#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Integration tests for API module.
"""

import unittest
import sys
import os
import json
import asyncio
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

# Add parent directory to path to import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from api import app
from base_phone_checker import PhoneCheckResult
from tests.mocks import MockDevice, create_mock_device_with_config, MockCache, create_predefined_cache_results


class TestAPI(unittest.TestCase):
    """Test cases for API module."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = TestClient(app)
        self.api_key = "test_key"
        
        # Mock environment variables
        os.environ["API_KEY"] = self.api_key
        os.environ["KASP_ADB_HOST"] = "127.0.0.1"
        os.environ["KASP_ADB_PORT"] = "5555"
        os.environ["TC_ADB_HOST"] = "127.0.0.1"
        os.environ["TC_ADB_PORT"] = "5556"
        os.environ["GC_ADB_HOST"] = "127.0.0.1"
        os.environ["GC_ADB_PORT"] = "5557"

    @patch('socket.create_connection')
    @patch('api.get_cache')
    @patch('uiautomator2.connect')
    def test_check_numbers_endpoint(self, mock_connect, mock_get_cache, mock_create_connection):
        """Test /check_numbers endpoint."""
        # Setup mocks
        mock_create_connection.return_value = MagicMock()
        
        # Mock cache
        mock_cache = MockCache()
        mock_get_cache.return_value = mock_cache
        
        # Mock device for Kaspersky
        kasp_config = {
            "elements": {
                "Check number": {"exists": True},
                "android.widget.EditText": {"exists": True},
                "Check": {"exists": True},
                "No feedback": {"exists": False},
                "SPAM": {"exists": False},
                "useful": {"exists": True, "text": "This number is useful"}
            }
        }
        mock_kasp_device = create_mock_device_with_config("127.0.0.1:5555", kasp_config)
        
        # Mock device for Truecaller
        tc_config = {
            "elements": {
                "searchBarLabel": {"exists": True},
                "search_field": {"exists": True},
                "searchWeb": {"exists": False},
                "SPAM": {"exists": True, "text": "SPAM!"},
                "nameOrNumber": {"exists": True, "text": "Spam Caller"},
                "numberDetails": {"exists": True, "text": "Mobile, Unknown"}
            }
        }
        mock_tc_device = create_mock_device_with_config("127.0.0.1:5556", tc_config)
        
        # Configure mock_connect to return different devices based on device_id
        def side_effect(device_id):
            if "5555" in device_id:
                return mock_kasp_device
            elif "5556" in device_id:
                return mock_tc_device
            else:
                raise ValueError(f"Unexpected device_id: {device_id}")
        
        mock_connect.side_effect = side_effect
        
        # Test endpoint
        response = self.client.post(
            "/check_numbers",
            json={"numbers": ["+79123456789", "+12025550108"], "use_cache": False},
            headers={"X-API-Key": self.api_key}
        )
        
        # Check response
        self.assertEqual(response.status_code, 200)
        self.assertIn("job_id", response.json())
        
        # Get job ID and check status
        job_id = response.json()["job_id"]
        
        # Wait for background task to complete (in real tests, we'd use async testing)
        # For this mock test, we'll just check that the job was created
        self.assertIsNotNone(job_id)

    @patch('api.get_cache')
    def test_check_numbers_with_cache(self, mock_get_cache):
        """Test /check_numbers endpoint with cache."""
        # Setup mock cache with predefined results
        mock_cache = MockCache(create_predefined_cache_results())
        mock_get_cache.return_value = mock_cache
        
        # Test endpoint
        response = self.client.post(
            "/check_numbers",
            json={"numbers": ["+79123456789", "+12025550108"], "use_cache": True},
            headers={"X-API-Key": self.api_key}
        )
        
        # Check response
        self.assertEqual(response.status_code, 200)
        self.assertIn("job_id", response.json())

    def test_check_numbers_unauthorized(self):
        """Test /check_numbers endpoint without API key."""
        response = self.client.post(
            "/check_numbers",
            json={"numbers": ["+79123456789"]}
        )
        self.assertEqual(response.status_code, 403)

    @patch('api.jobs')
    def test_get_status_endpoint(self, mock_jobs):
        """Test /status/{job_id} endpoint."""
        # Setup mock jobs
        job_id = "test_job_id"
        mock_jobs.__getitem__.return_value = {
            "status": "completed",
            "results": [
                {
                    "phone_number": "+79123456789",
                    "status": "Safe",
                    "details": "Test details",
                    "source": "Kaspersky"
                }
            ],
            "error": None,
            "progress": 100.0
        }
        mock_jobs.__contains__.return_value = True
        
        # Test endpoint
        response = self.client.get(
            f"/status/{job_id}",
            headers={"X-API-Key": self.api_key}
        )
        
        # Check response
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "completed")
        self.assertEqual(len(data["results"]), 1)
        self.assertEqual(data["results"][0]["phone_number"], "+79123456789")
        self.assertEqual(data["results"][0]["status"], "Safe")

    @patch('api.jobs')
    def test_get_status_not_found(self, mock_jobs):
        """Test /status/{job_id} endpoint with non-existent job."""
        # Setup mock jobs
        mock_jobs.__contains__.return_value = False
        
        # Test endpoint
        response = self.client.get(
            "/status/non_existent_job",
            headers={"X-API-Key": self.api_key}
        )
        
        # Check response
        self.assertEqual(response.status_code, 404)

    @patch('api.check_device_health')
    def test_device_status_endpoint(self, mock_check_device_health):
        """Test /device_status endpoint."""
        # Setup mock
        async def mock_health(device_id):
            if "5555" in device_id:
                return {"connected": True, "screen_on": True, "unlocked": True, "battery": "85%", "running_apps": "com.kaspersky.who_calls", "error": None}
            elif "5556" in device_id:
                return {"connected": True, "screen_on": True, "unlocked": True, "battery": "90%", "running_apps": "com.truecaller", "error": None}
            else:
                return {"connected": True, "screen_on": True, "unlocked": True, "battery": "95%", "running_apps": "app.source.getcontact", "error": None}
        
        mock_check_device_health.side_effect = mock_health
        
        # Test endpoint
        response = self.client.get(
            "/device_status",
            headers={"X-API-Key": self.api_key}
        )
        
        # Check response
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("kaspersky", data)
        self.assertIn("truecaller", data)
        self.assertIn("getcontact", data)

    @patch('api.get_cache')
    def test_clear_cache_endpoint(self, mock_get_cache):
        """Test /cache/clear endpoint."""
        # Setup mock
        mock_cache = MockCache()
        mock_get_cache.return_value = mock_cache
        
        # Test endpoint
        response = self.client.post(
            "/cache/clear",
            headers={"X-API-Key": self.api_key}
        )
        
        # Check response
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])

    def test_health_check_endpoint(self):
        """Test /health endpoint."""
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")


if __name__ == '__main__':
    unittest.main()

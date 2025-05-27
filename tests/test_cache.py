#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit tests for cache module.
"""

import unittest
import sys
import os
import asyncio
from unittest.mock import patch, MagicMock

# Add parent directory to path to import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from base_phone_checker import PhoneCheckResult
from cache import PhoneCheckerCache, CacheConfig


class TestPhoneCheckerCache(unittest.TestCase):
    """Test cases for PhoneCheckerCache."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a mock Redis client
        self.mock_redis = MagicMock()
        self.mock_redis.ping.return_value = True
        self.mock_redis.get.return_value = None
        self.mock_redis.setex.return_value = True
        self.mock_redis.delete.return_value = True
        self.mock_redis.pipeline.return_value = self.mock_redis
        self.mock_redis.execute.return_value = []

        # Create test config
        self.config = CacheConfig(
            redis_url="redis://localhost:6379/0",
            ttl=3600,
            enabled=True
        )

    @patch('redis.from_url')
    def test_init(self, mock_from_url):
        """Test initialization of PhoneCheckerCache."""
        # Setup mock
        mock_from_url.return_value = self.mock_redis

        # Test initialization
        cache = PhoneCheckerCache(self.config)
        self.assertEqual(cache.config, self.config)
        self.assertEqual(cache._redis, self.mock_redis)
        mock_from_url.assert_called_once_with(self.config.redis_url)

    @patch('redis.from_url')
    def test_init_disabled(self, mock_from_url):
        """Test initialization with disabled cache."""
        # Setup config
        config = CacheConfig(enabled=False)

        # Test initialization
        cache = PhoneCheckerCache(config)
        self.assertEqual(cache.config, config)
        self.assertIsNone(cache._redis)
        mock_from_url.assert_not_called()

    @patch('redis.from_url')
    def test_is_available(self, mock_from_url):
        """Test is_available property."""
        # Setup mock
        mock_from_url.return_value = self.mock_redis

        # Test with enabled cache
        cache = PhoneCheckerCache(self.config)
        self.assertTrue(cache.is_available)

        # Test with disabled cache
        config = CacheConfig(enabled=False)
        cache = PhoneCheckerCache(config)
        self.assertFalse(cache.is_available)

        # Test with Redis error
        self.mock_redis.ping.side_effect = Exception("Redis error")
        cache = PhoneCheckerCache(self.config)
        self.assertFalse(cache.is_available)

    @patch('redis.from_url')
    def test_get_key(self, mock_from_url):
        """Test _get_key method."""
        # Setup mock
        mock_from_url.return_value = self.mock_redis

        # Test key generation
        cache = PhoneCheckerCache(self.config)
        self.assertEqual(cache._get_key("+79123456789"), "phone_check:+79123456789")
        self.assertEqual(cache._get_key("+79123456789", "Kaspersky"), "phone_check:+79123456789:Kaspersky")

    @patch('redis.from_url')
    def test_get(self, mock_from_url):
        """Test get method."""
        # Setup mock
        mock_from_url.return_value = self.mock_redis
        self.mock_redis.get.return_value = '{"phone_number": "+79123456789", "status": "Safe", "details": "Test", "source": "Kaspersky"}'

        # Test get
        cache = PhoneCheckerCache(self.config)
        result = asyncio.run(cache.get("+79123456789", "Kaspersky"))
        self.assertIsNotNone(result)
        self.assertEqual(result.phone_number, "+79123456789")
        self.assertEqual(result.status, "Safe")
        self.assertEqual(result.details, "Test")
        self.assertEqual(result.source, "Kaspersky")
        self.mock_redis.get.assert_called_once_with("phone_check:+79123456789:Kaspersky")

    @patch('redis.from_url')
    def test_get_not_found(self, mock_from_url):
        """Test get method when key not found."""
        # Setup mock
        mock_from_url.return_value = self.mock_redis
        self.mock_redis.get.return_value = None

        # Test get with non-existent key
        cache = PhoneCheckerCache(self.config)
        result = asyncio.run(cache.get("+79123456789", "Kaspersky"))
        self.assertIsNone(result)
        self.mock_redis.get.assert_called_once_with("phone_check:+79123456789:Kaspersky")

    @patch('redis.from_url')
    def test_set(self, mock_from_url):
        """Test set method."""
        # Setup mock
        mock_from_url.return_value = self.mock_redis

        # Test set
        cache = PhoneCheckerCache(self.config)
        result = PhoneCheckResult(
            phone_number="+79123456789",
            status="Safe",
            details="Test",
            source="Kaspersky"
        )
        success = asyncio.run(cache.set(result))
        self.assertTrue(success)
        self.mock_redis.setex.assert_any_call(
            "phone_check:+79123456789:Kaspersky",
            self.config.ttl,
            '{"phone_number": "+79123456789", "status": "Safe", "details": "Test", "source": "Kaspersky"}'
        )
        self.mock_redis.setex.assert_any_call(
            "phone_check:+79123456789",
            self.config.ttl,
            '{"phone_number": "+79123456789", "status": "Safe", "details": "Test", "source": "Kaspersky"}'
        )

    @patch('redis.from_url')
    def test_delete(self, mock_from_url):
        """Test delete method."""
        # Setup mock
        mock_from_url.return_value = self.mock_redis

        # Test delete
        cache = PhoneCheckerCache(self.config)
        success = asyncio.run(cache.delete("+79123456789", "Kaspersky"))
        self.assertTrue(success)
        self.mock_redis.delete.assert_called_once_with("phone_check:+79123456789:Kaspersky")

    @patch('redis.from_url')
    def test_get_multiple(self, mock_from_url):
        """Test get_multiple method."""
        # Setup mock
        mock_from_url.return_value = self.mock_redis
        self.mock_redis.execute.return_value = [
            '{"phone_number": "+79123456789", "status": "Safe", "details": "Test1", "source": "Kaspersky"}',
            None,
            '{"phone_number": "+79123456791", "status": "Spam", "details": "Test3", "source": "Kaspersky"}'
        ]

        # Test get_multiple
        cache = PhoneCheckerCache(self.config)
        results = asyncio.run(cache.get_multiple(["+79123456789", "+79123456790", "+79123456791"], "Kaspersky"))
        self.assertEqual(len(results), 2)
        self.assertIn("+79123456789", results)
        self.assertIn("+79123456791", results)
        self.assertEqual(results["+79123456789"].status, "Safe")
        self.assertEqual(results["+79123456791"].status, "Spam")

    @patch('redis.from_url')
    def test_set_multiple(self, mock_from_url):
        """Test set_multiple method."""
        # Setup mock
        mock_from_url.return_value = self.mock_redis

        # Test set_multiple
        cache = PhoneCheckerCache(self.config)
        results = [
            PhoneCheckResult(phone_number="+79123456789", status="Safe", details="Test1", source="Kaspersky"),
            PhoneCheckResult(phone_number="+79123456790", status="Spam", details="Test2", source="Kaspersky")
        ]
        success = asyncio.run(cache.set_multiple(results))
        self.assertTrue(success)
        self.mock_redis.pipeline.assert_called_once()
        self.mock_redis.execute.assert_called_once()

    @patch('redis.from_url')
    def test_clear_all(self, mock_from_url):
        """Test clear_all method."""
        # Setup mock
        mock_from_url.return_value = self.mock_redis
        self.mock_redis.scan_iter.return_value = ["phone_check:+79123456789", "phone_check:+79123456790"]

        # Test clear_all
        cache = PhoneCheckerCache(self.config)
        success = asyncio.run(cache.clear_all())
        self.assertTrue(success)
        self.mock_redis.scan_iter.assert_called_once_with("phone_check:*")
        self.mock_redis.delete.assert_called_once()


if __name__ == '__main__':
    unittest.main()

#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: conftest.py
Version: 1.0.0
Last Updated: 2025-12-06
Purpose: Pytest configuration and fixtures for trading service tests

Description:
Provides shared fixtures and configuration for all trading service tests.
"""

import pytest
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Set up mock environment variables for testing."""
    monkeypatch.setenv("ALPACA_API_KEY", "test_key")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "test_secret")
    monkeypatch.setenv("TRADING_MODE", "paper")

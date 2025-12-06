#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: test_order_side.py
Version: 1.0.0
Last Updated: 2025-12-06
Purpose: Integration test for order side mapping

REVISION HISTORY:
v1.0.0 (2025-12-06) - Initial integration test
- Tests order side mapping via trading service endpoint
- Verifies long->buy and short->sell mappings
- Can run before each trading session for verification

Description:
This script tests the order side mapping by calling the trading service's
/api/v1/orders/test endpoint. It verifies that:
- "long" correctly maps to "buy"
- "short" correctly maps to "sell"
- "buy" passes through as "buy"
- "sell" passes through as "sell"

Usage:
    python scripts/test_order_side.py

The v1.2.0 bug caused "long" to map to "sell", resulting in inverted positions.
This test ensures that bug never happens again.
"""

import sys
import requests
import json
from datetime import datetime

# Configuration
TRADING_SERVICE_URL = "http://localhost:5005"
TEST_ENDPOINT = "/api/v1/orders/test"


def test_side_mapping(side: str, expected: str) -> bool:
    """
    Test a single side mapping.

    Args:
        side: Input side to test ("long", "short", "buy", "sell")
        expected: Expected mapped side ("buy" or "sell")

    Returns:
        True if test passed, False otherwise
    """
    try:
        response = requests.post(
            f"{TRADING_SERVICE_URL}{TEST_ENDPOINT}",
            json={
                "symbol": "TEST",
                "quantity": 1,
                "side": side,
                "dry_run": True
            },
            timeout=5
        )

        if response.status_code != 200:
            print(f"  FAIL: HTTP {response.status_code} - {response.text}")
            return False

        result = response.json()
        mapped_side = result.get("mapped_side")

        if mapped_side == expected:
            print(f"  PASS: '{side}' -> '{mapped_side}' (expected '{expected}')")
            return True
        else:
            print(f"  FAIL: '{side}' -> '{mapped_side}' (expected '{expected}')")
            return False

    except requests.exceptions.ConnectionError:
        print(f"  FAIL: Cannot connect to trading service at {TRADING_SERVICE_URL}")
        return False
    except Exception as e:
        print(f"  FAIL: {e}")
        return False


def run_all_tests() -> bool:
    """
    Run all order side mapping tests.

    Returns:
        True if all tests passed, False otherwise
    """
    print("=" * 60)
    print("ORDER SIDE MAPPING INTEGRATION TEST")
    print(f"Trading Service: {TRADING_SERVICE_URL}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("=" * 60)
    print()

    # Check service health first
    try:
        health = requests.get(f"{TRADING_SERVICE_URL}/health", timeout=5)
        if health.status_code != 200:
            print("ERROR: Trading service health check failed")
            return False
        health_data = health.json()
        print(f"Service: {health_data.get('service')} v{health_data.get('version')}")
        print(f"Status: {health_data.get('status')}")
        print()
    except Exception as e:
        print(f"ERROR: Cannot reach trading service: {e}")
        return False

    # Test cases - these are the critical mappings
    test_cases = [
        # (input_side, expected_output)
        ("long", "buy"),    # CRITICAL: This was the v1.2.0 bug
        ("LONG", "buy"),    # Case insensitive
        ("Long", "buy"),    # Mixed case
        ("short", "sell"),  # Short positions
        ("SHORT", "sell"),  # Case insensitive
        ("buy", "buy"),     # Direct mapping
        ("BUY", "buy"),     # Case insensitive
        ("sell", "sell"),   # Direct mapping
        ("SELL", "sell"),   # Case insensitive
    ]

    print("Running test cases:")
    print("-" * 40)

    passed = 0
    failed = 0

    for side, expected in test_cases:
        if test_side_mapping(side, expected):
            passed += 1
        else:
            failed += 1

    print("-" * 40)
    print()

    # Test invalid input (should fail)
    print("Testing invalid input (expecting error):")
    print("-" * 40)
    try:
        response = requests.post(
            f"{TRADING_SERVICE_URL}{TEST_ENDPOINT}",
            json={
                "symbol": "TEST",
                "quantity": 1,
                "side": "invalid",
                "dry_run": True
            },
            timeout=5
        )
        if response.status_code == 400:
            print("  PASS: Invalid side correctly rejected with 400")
            passed += 1
        else:
            print(f"  FAIL: Invalid side should return 400, got {response.status_code}")
            failed += 1
    except Exception as e:
        print(f"  FAIL: {e}")
        failed += 1

    print("-" * 40)
    print()

    # Summary
    print("=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Total:  {passed + failed}")
    print()

    if failed == 0:
        print("RESULT: ALL TESTS PASSED")
        print()
        print("The order side bug (v1.2.0) fix is working correctly.")
        print("'long' correctly maps to 'buy' (not 'sell').")
        return True
    else:
        print("RESULT: SOME TESTS FAILED")
        print()
        print("WARNING: Order side mapping may be incorrect!")
        print("DO NOT proceed with trading until this is fixed.")
        return False


def main():
    """Main entry point."""
    success = run_all_tests()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

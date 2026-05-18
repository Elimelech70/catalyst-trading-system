"""
Broker integrations for the Catalyst Trading Agent.

This package provides broker connectivity for:
- Moomoo for HKEX trading via OpenD gateway
"""

from brokers.moomoo import MoomooClient, get_moomoo_client, init_moomoo_client

__all__ = ["MoomooClient", "get_moomoo_client", "init_moomoo_client"]

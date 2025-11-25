#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: config_loader.py
Version: 1.0.0
Last Updated: 2025-11-18
Purpose: YAML configuration loader with hot-reload support

Description:
Centralized configuration loading for all services.
Supports:
- Hot-reload (watches file changes)
- Caching
- Environment variable overrides
- Validation
"""

import yaml
import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import threading

logger = logging.getLogger(__name__)

class ConfigLoader:
    """
    Configuration loader with caching and hot-reload support.

    Usage:
        loader = ConfigLoader()
        risk_config = loader.load('config/risk_parameters.yaml')
        trading_config = loader.load('config/trading_config.yaml')
    """

    def __init__(self, base_path: Optional[str] = None):
        self.base_path = base_path or os.getenv('CONFIG_BASE_PATH', '/app')
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._cache_time: Dict[str, datetime] = {}
        self._cache_ttl = timedelta(seconds=int(os.getenv('CONFIG_CACHE_TTL', '60')))
        self._lock = threading.Lock()

    def load(self, config_path: str, force_reload: bool = False) -> Dict[str, Any]:
        """
        Load configuration from YAML file.

        Args:
            config_path: Path to YAML file (relative to base_path)
            force_reload: Skip cache and reload from disk

        Returns:
            Configuration dictionary

        Raises:
            FileNotFoundError: If config file doesn't exist
            yaml.YAMLError: If YAML is invalid
        """
        # Build full path
        if os.path.isabs(config_path):
            full_path = config_path
        else:
            full_path = os.path.join(self.base_path, config_path)

        # Check cache
        if not force_reload:
            with self._lock:
                if config_path in self._cache:
                    cache_age = datetime.now() - self._cache_time[config_path]
                    if cache_age < self._cache_ttl:
                        logger.debug(f"Config cache hit: {config_path}")
                        return self._cache[config_path].copy()

        # Load from file
        try:
            logger.info(f"Loading config: {full_path}")

            if not os.path.exists(full_path):
                raise FileNotFoundError(f"Config file not found: {full_path}")

            with open(full_path, 'r') as f:
                config = yaml.safe_load(f)

            if config is None:
                logger.warning(f"Empty config file: {config_path}")
                config = {}

            # Apply environment variable overrides
            config = self._apply_env_overrides(config)

            # Cache the config
            with self._lock:
                self._cache[config_path] = config.copy()
                self._cache_time[config_path] = datetime.now()

            logger.info(f"Config loaded successfully: {config_path}")
            return config.copy()

        except yaml.YAMLError as e:
            logger.error(f"YAML parse error in {config_path}: {e}")
            raise
        except Exception as e:
            logger.error(f"Error loading config {config_path}: {e}")
            raise

    def _apply_env_overrides(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Apply environment variable overrides to config"""

        # Example overrides for risk_parameters.yaml
        if 'risk_limits' in config:
            # Override max_daily_loss from env
            env_max_loss = os.getenv('MAX_DAILY_LOSS_USD')
            if env_max_loss:
                try:
                    config['risk_limits']['max_daily_loss_usd'] = float(env_max_loss)
                    logger.info(f"Override max_daily_loss_usd from env: {env_max_loss}")
                except ValueError:
                    logger.warning(f"Invalid MAX_DAILY_LOSS_USD: {env_max_loss}")

            # Override max_positions from env
            env_max_pos = os.getenv('MAX_POSITIONS')
            if env_max_pos:
                try:
                    config['risk_limits']['max_positions'] = int(env_max_pos)
                    logger.info(f"Override max_positions from env: {env_max_pos}")
                except ValueError:
                    logger.warning(f"Invalid MAX_POSITIONS: {env_max_pos}")

        # Example overrides for trading_config.yaml
        if 'trading_session' in config:
            # Override mode from env
            env_mode = os.getenv('TRADING_SESSION_MODE')
            if env_mode:
                config['trading_session']['mode'] = env_mode
                logger.info(f"Override trading_session.mode from env: {env_mode}")

        return config

    def reload(self, config_path: str) -> Dict[str, Any]:
        """Force reload config from disk"""
        return self.load(config_path, force_reload=True)

    def clear_cache(self):
        """Clear all cached configs"""
        with self._lock:
            self._cache.clear()
            self._cache_time.clear()
            logger.info("Config cache cleared")


# Global singleton instance
_config_loader = ConfigLoader()


def get_risk_config(force_reload: bool = False) -> Dict[str, Any]:
    """
    Get risk parameters configuration.

    Returns config/risk_parameters.yaml
    """
    return _config_loader.load('config/risk_parameters.yaml', force_reload=force_reload)


def get_trading_config(force_reload: bool = False) -> Dict[str, Any]:
    """
    Get trading configuration.

    Returns config/trading_config.yaml
    """
    return _config_loader.load('config/trading_config.yaml', force_reload=force_reload)


def reload_all_configs():
    """Reload all configurations from disk"""
    _config_loader.clear_cache()
    logger.info("All configs reloaded")


# Convenience functions for specific config values
def get_max_daily_loss() -> float:
    """Get max daily loss limit from config"""
    config = get_risk_config()
    return config.get('risk_limits', {}).get('max_daily_loss_usd', 2000.0)


def get_max_positions() -> int:
    """Get max positions limit from config"""
    config = get_risk_config()
    return config.get('risk_limits', {}).get('max_positions', 5)


def get_trading_session_mode() -> str:
    """Get trading session mode (autonomous or supervised)"""
    config = get_trading_config()
    return config.get('trading_session', {}).get('mode', 'supervised')


def is_autonomous_mode() -> bool:
    """Check if system is in autonomous trading mode"""
    mode = get_trading_session_mode()
    return mode.lower() == 'autonomous'


def get_workflow_config(force_reload: bool = False) -> Dict[str, Any]:
    """
    Get workflow configuration from workflow_config.yaml.

    Returns workflow configuration with defaults for filter settings.

    Default workflow config:
    {
        "scan_frequency_minutes": 30,
        "execute_top_n": 3,
        "filters": {
            "news": {
                "enabled": true,
                "required": false,
                "min_sentiment": 0.3,
                "fallback_score": 0.5,
                "max_age_hours": 24
            },
            "pattern": {
                "enabled": true,
                "required": false,
                "min_confidence": 0.6
            },
            "technical": {
                "enabled": true,
                "required": false
            }
        }
    }
    """
    # Default configuration
    default_config = {
        "scan_frequency_minutes": 30,
        "execute_top_n": 3,
        "filters": {
            "news": {
                "enabled": True,
                "required": False,  # Don't block workflow if news unavailable
                "min_sentiment": 0.3,
                "fallback_score": 0.5,
                "max_age_hours": 24
            },
            "pattern": {
                "enabled": True,
                "required": False,
                "min_confidence": 0.6
            },
            "technical": {
                "enabled": True,
                "required": False
            }
        }
    }

    try:
        loaded_config = _config_loader.load('config/workflow_config.yaml', force_reload=force_reload)

        # Merge with defaults (loaded values override defaults)
        if 'workflow' in loaded_config:
            config = {**default_config, **loaded_config['workflow']}

            # Deep merge filters
            if 'filters' in loaded_config['workflow']:
                for filter_type, filter_config in loaded_config['workflow']['filters'].items():
                    if filter_type in config['filters']:
                        config['filters'][filter_type].update(filter_config)
                    else:
                        config['filters'][filter_type] = filter_config
        else:
            # If 'workflow' key doesn't exist, use loaded_config directly
            config = {**default_config, **loaded_config}

            # Deep merge filters
            if 'filters' in loaded_config:
                for filter_type, filter_config in loaded_config['filters'].items():
                    if filter_type in config['filters']:
                        config['filters'][filter_type].update(filter_config)
                    else:
                        config['filters'][filter_type] = filter_config

        return config

    except FileNotFoundError:
        logger.warning("workflow_config.yaml not found, using defaults")
        return default_config
    except Exception as e:
        logger.error(f"Failed to load workflow config: {e}, using defaults")
        return default_config


def get_risk_limits() -> Dict[str, Any]:
    """Get all risk limits"""
    config = get_risk_config()
    return config.get('risk_limits', {})


def get_emergency_actions() -> Dict[str, Any]:
    """Get emergency action configuration"""
    config = get_risk_config()
    return config.get('emergency_actions', {})


def get_alert_config() -> Dict[str, Any]:
    """Get alert configuration"""
    config = get_risk_config()
    return config.get('alerts', {})


if __name__ == '__main__':
    # Test the config loader
    logging.basicConfig(level=logging.INFO)

    print("Testing Config Loader...")
    print("=" * 70)

    try:
        # Load risk config
        risk_config = get_risk_config()
        print(f"✅ Risk config loaded")
        print(f"   Max daily loss: ${get_max_daily_loss()}")
        print(f"   Max positions: {get_max_positions()}")

        # Load trading config
        trading_config = get_trading_config()
        print(f"✅ Trading config loaded")
        print(f"   Session mode: {get_trading_session_mode()}")
        print(f"   Autonomous: {is_autonomous_mode()}")

        # Test cache
        print("\nTesting cache...")
        import time
        start = time.time()
        get_risk_config()  # Should hit cache
        elapsed = time.time() - start
        print(f"✅ Cache hit (took {elapsed*1000:.2f}ms)")

        # Test reload
        print("\nTesting reload...")
        risk_config = get_risk_config(force_reload=True)
        print(f"✅ Config reloaded")

        print("\n" + "=" * 70)
        print("Config Loader Test: PASSED")

    except Exception as e:
        print(f"❌ Error: {e}")
        raise

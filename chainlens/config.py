"""Configuration for ChainLens."""

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ChainLensConfig:
    """Central config for all ChainLens modules."""

    # RPC
    rpc_url: str = os.getenv("CHAINLENS_RPC_URL", "https://eth-mainnet.g.alchemy.com/v2/YOUR_KEY")
    ws_url: Optional[str] = os.getenv("CHAINLENS_WS_URL")
    chain_id: int = int(os.getenv("CHAINLENS_CHAIN_ID", "1"))
    poll_interval: float = float(os.getenv("CHAINLENS_POLL_INTERVAL", "12.0"))

    # Alerting
    telegram_bot_token: Optional[str] = os.getenv("TELEGRAM_BOT_TOKEN")
    telegram_chat_id: Optional[str] = os.getenv("TELEGRAM_CHAT_ID")
    discord_webhook_url: Optional[str] = os.getenv("DISCORD_WEBHOOK_URL")

    # Whale tracking
    whale_threshold_eth: float = float(os.getenv("CHAINLENS_WHALE_ETH", "100"))
    whale_addresses: list = field(default_factory=list)

    # Tracing
    log_level: str = os.getenv("CHAINLENS_LOG_LEVEL", "INFO")

    @classmethod
    def from_env(cls) -> "ChainLensConfig":
        """Load config from environment variables."""
        return cls()

    def validate(self) -> list[str]:
        """Return list of missing required fields."""
        issues = []
        if "YOUR_KEY" in self.rpc_url:
            issues.append("rpc_url: placeholder key detected")
        if not self.ws_url:
            issues.append("ws_url not set (websocket mode unavailable)")
        return issues

"""Whale tracker — monitors ERC-20 transfers for large movements."""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Optional

import aiohttp

from chainlens.config import ChainLensConfig

logger = logging.getLogger("chainlens.whale")

# ERC-20 Transfer event topic
TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"


@dataclass
class TransferEvent:
    token: str
    from_addr: str
    to_addr: str
    value: int
    tx_hash: str
    block: int
    timestamp: Optional[datetime] = None

    @property
    def value_normalized(self) -> float:
        """Assumes 18 decimals; override per-token for accuracy."""
        return self.value / 1e18


@dataclass
class WhaleAlert:
    transfer: TransferEvent
    direction: str  # "inflow" or "outflow"
    label: str = ""


class WhaleTracker:
    """Watches ERC-20 Transfer logs and fires callbacks on large moves."""

    def __init__(self, config: Optional[ChainLensConfig] = None):
        self.config = config or ChainLensConfig()
        self._session: Optional[aiohttp.ClientSession] = None
        self._callbacks: list[Callable] = []
        self._watched_tokens: set[str] = set()
        self._watched_whales: set[str] = set()
        self._running = False

    # ── Setup ─────────────────────────────────────────────────────

    def watch_token(self, address: str):
        """Add an ERC-20 token address to monitor."""
        self._watched_tokens.add(address.lower())

    def watch_whale(self, address: str):
        """Add a whale address to monitor."""
        self._watched_whales.add(address.lower())

    def on_whale_move(self, callback: Callable):
        """Register a callback for whale movements."""
        self._callbacks.append(callback)
        return callback

    # ── RPC helpers ───────────────────────────────────────────────

    async def _ensure_session(self):
        if not self._session:
            self._session = aiohttp.ClientSession()

    async def _get_logs(self, from_block: int, to_block: int,
                        address: Optional[str] = None) -> list[dict]:
        await self._ensure_session()
        params: dict = {
            "fromBlock": hex(from_block),
            "toBlock": hex(to_block),
            "topics": [TRANSFER_TOPIC],
        }
        if address:
            params["address"] = address
        payload = {"jsonrpc": "2.0", "method": "eth_getLogs", "params": [params], "id": 1}
        async with self._session.post(self.config.rpc_url, json=payload) as resp:
            data = await resp.json()
            return data.get("result", [])

    async def _get_block_number(self) -> int:
        await self._ensure_session()
        payload = {"jsonrpc": "2.0", "method": "eth_blockNumber", "params": [], "id": 1}
        async with self._session.post(self.config.rpc_url, json=payload) as resp:
            data = await resp.json()
            return int(data.get("result", "0x0"), 16)

    # ── Parsing ───────────────────────────────────────────────────

    @staticmethod
    def _parse_log(log: dict) -> Optional[TransferEvent]:
        topics = log.get("topics", [])
        if len(topics) < 3:
            return None
        from_addr = "0x" + topics[1][-40:]
        to_addr = "0x" + topics[2][-40:]
        data = log.get("data", "0x")
        value = int(data, 16) if data != "0x" else 0
        return TransferEvent(
            token=log.get("address", "").lower(),
            from_addr=from_addr.lower(),
            to_addr=to_addr.lower(),
            value=value,
            tx_hash=log.get("transactionHash", ""),
            block=int(log.get("blockNumber", "0x0"), 16),
        )

    # ── Core loop ─────────────────────────────────────────────────

    async def _notify(self, alert: WhaleAlert):
        for cb in self._callbacks:
            try:
                if asyncio.iscoroutinefunction(cb):
                    await cb(alert)
                else:
                    cb(alert)
            except Exception as exc:
                logger.error("Whale callback error: %s", exc)

    async def poll(self, lookback: int = 100):
        """Poll recent blocks for large transfers."""
        current = await self._get_block_number()
        from_block = max(0, current - lookback)
        addresses = list(self._watched_tokens) if self._watched_tokens else None
        logs = await self._get_logs(from_block, current, addresses[0] if addresses and len(addresses) == 1 else None)

        for log in logs:
            event = self._parse_log(log)
            if not event:
                continue

            # Filter by watched tokens if multiple specified
            if self._watched_tokens and event.token not in self._watched_tokens:
                continue

            # Check value threshold
            value_eth = event.value / 1e18
            if value_eth < self.config.whale_threshold_eth:
                continue

            direction = "outflow" if event.from_addr in self._watched_whales else "inflow"
            if event.to_addr not in self._watched_whales and direction == "outflow" and event.from_addr not in self._watched_whales:
                continue

            alert = WhaleAlert(transfer=event, direction=direction)
            logger.info("🐋 Whale %s: %.2f ETH (%s → %s) tx=%s",
                        direction, value_eth, event.from_addr[:10], event.to_addr[:10], event.tx_hash[:10])
            await self._notify(alert)

    async def start(self, lookback: int = 100, interval: float = 30):
        """Continuously poll for whale moves."""
        self._running = True
        logger.info("Whale tracker started — threshold %.1f ETH", self.config.whale_threshold_eth)
        while self._running:
            try:
                await self.poll(lookback)
            except Exception as exc:
                logger.warning("Whale poll error: %s", exc)
            await asyncio.sleep(interval)

    async def stop(self):
        self._running = False
        if self._session:
            await self._session.close()
        logger.info("Whale tracker stopped")

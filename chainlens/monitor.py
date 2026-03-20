"""EVM Block Monitor — websocket + polling modes."""

import asyncio
import json
import logging
import time
from typing import Callable, Optional

import aiohttp

from chainlens.config import ChainLensConfig

logger = logging.getLogger("chainlens.monitor")


class BlockMonitor:
    """Monitors new EVM blocks via WebSocket subscription or HTTP polling."""

    def __init__(self, config: Optional[ChainLensConfig] = None):
        self.config = config or ChainLensConfig()
        self._running = False
        self._callbacks: list[Callable] = []
        self._session: Optional[aiohttp.ClientSession] = None

    def on_block(self, callback: Callable):
        """Register a callback for new blocks."""
        self._callbacks.append(callback)
        return callback

    async def _notify(self, block_data: dict):
        for cb in self._callbacks:
            try:
                if asyncio.iscoroutinefunction(cb):
                    await cb(block_data)
                else:
                    cb(block_data)
            except Exception as exc:
                logger.error("Callback error: %s", exc)

    # ── Polling mode ──────────────────────────────────────────────

    async def _fetch_block(self, block_num: str = "latest") -> dict:
        payload = {
            "jsonrpc": "2.0",
            "method": "eth_getBlockByNumber",
            "params": [block_num, True],
            "id": 1,
        }
        async with self._session.post(self.config.rpc_url, json=payload) as resp:
            data = await resp.json()
            return data.get("result", {})

    async def _poll_loop(self):
        last_block = 0
        while self._running:
            try:
                block = await self._fetch_block("latest")
                block_num = int(block.get("number", "0x0"), 16)
                if block_num > last_block:
                    last_block = block_num
                    logger.info("New block #%d (%d txs)", block_num, len(block.get("transactions", [])))
                    await self._notify(block)
                await asyncio.sleep(self.config.poll_interval)
            except Exception as exc:
                logger.warning("Poll error: %s — retrying in 5s", exc)
                await asyncio.sleep(5)

    # ── WebSocket mode ────────────────────────────────────────────

    async def _ws_loop(self):
        ws_url = self.config.ws_url or self.config.rpc_url.replace("https", "wss")
        while self._running:
            try:
                async with self._session.ws_connect(ws_url) as ws:
                    sub_msg = json.dumps({
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "eth_subscribe",
                        "params": ["newHeads"],
                    })
                    await ws.send_str(sub_msg)
                    logger.info("WebSocket subscribed to newHeads")

                    async for msg in ws:
                        if not self._running:
                            break
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            data = json.loads(msg.data)
                            result = data.get("params", {}).get("result", {})
                            if result:
                                await self._notify(result)
                        elif msg.type == aiohttp.WSMsgType.ERROR:
                            logger.error("WS error: %s", ws.exception())
                            break
            except Exception as exc:
                logger.warning("WS connection lost: %s — reconnecting in 5s", exc)
                await asyncio.sleep(5)

    # ── Lifecycle ─────────────────────────────────────────────────

    async def start(self, mode: str = "auto"):
        """Start monitoring. mode: 'ws', 'poll', or 'auto'."""
        issues = self.config.validate()
        if issues:
            for i in issues:
                logger.warning("Config: %s", i)

        self._session = aiohttp.ClientSession()
        self._running = True

        if mode == "auto":
            mode = "ws" if self.config.ws_url else "poll"

        logger.info("Starting block monitor in %s mode (chain %d)", mode, self.config.chain_id)
        if mode == "ws":
            await self._ws_loop()
        else:
            await self._poll_loop()

    async def stop(self):
        self._running = False
        if self._session:
            await self._session.close()
        logger.info("Block monitor stopped")

    # ── Sync helper ───────────────────────────────────────────────

    def run(self, mode: str = "auto"):
        """Blocking entrypoint."""
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(self.start(mode))
        except KeyboardInterrupt:
            loop.run_until_complete(self.stop())
        finally:
            loop.close()

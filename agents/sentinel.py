"""Sentinel Agent — all-in-one monitoring agent.

Combines block monitoring, whale tracking, contract analysis, and alerts
into a single autonomous agent.

Usage:
    CHAINLENS_RPC_URL=https://... python agents/sentinel.py
"""

import asyncio
import logging
from datetime import datetime, timezone

from chainlens.config import ChainLensConfig
from chainlens.monitor import BlockMonitor
from chainlens.whale_tracker import WhaleTracker, WhaleAlert
from chainlens.analyzer import ContractAnalyzer
from chainlens.alerts import AlertManager, Alert
from chainlens.trading_signals import TradingSignalGenerator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("sentinel")


class SentinelAgent:
    """Unified monitoring agent — watches everything, alerts on everything."""

    def __init__(self, config: ChainLensConfig):
        self.config = config
        self.monitor = BlockMonitor(config)
        self.whales = WhaleTracker(config)
        self.analyzer = ContractAnalyzer(config)
        self.alerts = AlertManager(config)
        self.signals = TradingSignalGenerator()
        self._block_count = 0
        self._start_time = None

    async def _on_block(self, block: dict):
        block_num = int(block.get("number", "0x0"), 16)
        txs = block.get("transactions", [])
        self._block_count += 1

        logger.info("Block #%d — %d txs (total watched: %d)", block_num, len(txs), self._block_count)

        # Check for new contract deployments
        for tx in txs:
            to_addr = tx.get("to")
            if to_addr is None:
                # Contract creation
                logger.info("🔍 New contract deployment detected in block #%d", block_num)
                receipt_data = tx.get("hash", "")
                await self.alerts.send(Alert(
                    title="New Contract Deployment",
                    body=f"Deployed in block #{block_num}\nTx: {receipt_data}",
                    severity="info",
                    source="block_monitor",
                ))

    async def _on_whale_move(self, alert: WhaleAlert):
        t = alert.transfer
        severity = "critical" if t.value_normalized > 5_000_000 else "warning"
        await self.alerts.send(Alert(
            title=f"🐋 Whale {alert.direction.upper()}",
            body=f"{t.value_normalized:,.2f} tokens\n"
                 f"From: {t.from_addr[:20]}...\nTo: {t.to_addr[:20]}...\n"
                 f"Tx: {t.tx_hash[:20]}...",
            severity=severity,
            source="whale_tracker",
        ))

    async def start(self):
        """Start all monitoring subsystems."""
        self._start_time = datetime.now(timezone.utc)

        # Wire up callbacks
        self.monitor.on_block(self._on_block)
        self.whales.on_whale_move(self._on_whale_move)

        logger.info("=" * 60)
        logger.info("🛡️  Sentinel Agent starting")
        logger.info("Chain: %d | RPC: %s", self.config.chain_id, self.config.rpc_url[:40])
        logger.info("Whale threshold: %.1f ETH", self.config.whale_threshold_eth)
        logger.info("=" * 60)

        # Run block monitor and whale tracker concurrently
        await asyncio.gather(
            self.monitor.start(),
            self.whales.start(),
        )

    async def stop(self):
        """Shutdown all subsystems."""
        logger.info("Sentinel stopping...")
        await self.monitor.stop()
        await self.whales.stop()
        await self.analyzer.close()
        await self.alerts.close()
        uptime = datetime.now(timezone.utc) - self._start_time if self._start_time else None
        logger.info("🛡️  Sentinel stopped. Uptime: %s | Blocks watched: %d", uptime, self._block_count)


async def main():
    config = ChainLensConfig.from_env()
    agent = SentinelAgent(config)
    try:
        await agent.start()
    except KeyboardInterrupt:
        await agent.stop()


if __name__ == "__main__":
    asyncio.run(main())

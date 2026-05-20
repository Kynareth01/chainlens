"""Whale alert bot — monitors ERC-20 transfers and sends alerts.

Usage:
    CHAINLENS_RPC_URL=https://... \
    TELEGRAM_BOT_TOKEN=... \
    TELEGRAM_CHAT_ID=... \
    python examples/whale_alert_bot.py
"""

import asyncio
from chainlens.config import ChainLensConfig
from chainlens.whale_tracker import WhaleTracker, WhaleAlert
from chainlens.alerts import AlertManager, Alert


async def main():
    config = ChainLensConfig.from_env()
    alerts = AlertManager(config)
    tracker = WhaleTracker(config)

    # Add some well-known whale addresses (examples — replace with real ones)
    tracker.watch_whale("0x28c6c06298d514db089934071355e5743bf21d60")  # Binance 14
    tracker.watch_whale("0x21a31ee1afc51d94c2efccaa2092ad1028285549")  # Binance 36
    tracker.watch_whale("0xdfd5293d8e347dfe59e90efd55b2956a1343963d")  # Binance 16

    # Track USDT and USDC
    tracker.watch_token("0xdac17f958d2ee523a2206206994597c13d831ec7")  # USDT
    tracker.watch_token("0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48")  # USDC

    @tracker.on_whale_move
    async def send_alert(whale_alert: WhaleAlert):
        t = whale_alert.transfer
        alert = Alert(
            title=f"🐋 Whale {whale_alert.direction.upper()}",
            body=f"{t.value_normalized:,.2f} tokens\n"
                 f"From: {t.from_addr}\nTo: {t.to_addr}\n"
                 f"Tx: {t.tx_hash}",
            severity="warning" if t.value_normalized > 1_000_000 else "info",
            source=f"token:{t.token}",
        )
        await alerts.send(alert)
        print(f"🚨 Alert sent: {whale_alert.direction} {t.value_normalized:,.2f}")

    print("🐋 Whale alert bot starting...")
    print(f"Threshold: {config.whale_threshold_eth} ETH")
    try:
        await tracker.start(lookback=50, interval=30)
    except KeyboardInterrupt:
        await tracker.stop()
        await alerts.close()


if __name__ == "__main__":
    asyncio.run(main())

"""Basic block monitor example.

Usage:
    CHAINLENS_RPC_URL=https://your-rpc-url python examples/basic_monitor.py
"""

import asyncio
from chainlens import BlockMonitor, ChainLensConfig


async def main():
    config = ChainLensConfig.from_env()
    monitor = BlockMonitor(config)

    @monitor.on_block
    async def on_block(block):
        block_num = int(block.get("number", "0x0"), 16)
        tx_count = len(block.get("transactions", []))
        gas_used = int(block.get("gasUsed", "0x0"), 16)
        print(f"⛏️  Block #{block_num:,} — {tx_count} txs — gas {gas_used:,}")

    print("Starting ChainLens block monitor...")
    print(f"RPC: {config.rpc_url[:40]}...")
    try:
        await monitor.start()
    except KeyboardInterrupt:
        await monitor.stop()


if __name__ == "__main__":
    asyncio.run(main())

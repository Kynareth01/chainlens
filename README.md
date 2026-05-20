# ChainLens

I got rugged twice. Second time I built this.

ChainLens is an EVM blockchain monitoring agent that watches on-chain activity so you don't have to. It tracks whale movements, audits smart contracts, detects rug-pull patterns, and generates trading signals — all from your own node or RPC endpoint.

## Features

- **Block Monitor** — Real-time EVM block monitoring via WebSocket or HTTP polling with automatic reconnection and exponential backoff
- **Contract Analyzer** — Fetches and decompiles contract bytecode, extracts function selectors, and generates risk scores based on dangerous patterns (selfdestruct, delegatecall, tx.origin)
- **Whale Tracker** — Monitors ERC-20 Transfer events for large movements, configurable threshold per token
- **Alerts** — Telegram bot and Discord webhook integration for real-time notifications
- **Trading Signals** — SMA/EMA crossovers, RSI, Bollinger Bands, plus whale-activity confidence boosters
- **Dashboard** — Streamlit + Plotly interactive dashboard with price charts, signal overlays, and whale activity feeds
- **Portfolio Tracker** — Fetch native + ERC-20 balances across multiple wallets concurrently

## Quick Start

```bash
pip install chainlens

# or from source
git clone https://github.com/Kynareth01/chainlens.git
cd chainlens
pip install -e ".[dashboard]"
```

### Environment

```bash
cp .env.example .env
# Edit .env with your RPC URL, Telegram/Discord credentials
```

### Run the monitor

```python
from chainlens import BlockMonitor, ChainLensConfig

config = ChainLensConfig.from_env()
monitor = BlockMonitor(config)

@monitor.on_block
async def handle_block(block):
    print(f"Block #{int(block['number'], 16)}")

monitor.run()
```

### Run the dashboard

```bash
streamlit run chainlens/dashboard.py
```

## Docker

```bash
docker-compose up -d
```

## Project Structure

```
chainlens/
├── __init__.py          # Package init + exports
├── config.py            # Central configuration (env-based)
├── monitor.py           # EVM block monitor (WS + polling)
├── analyzer.py          # Contract bytecode analyzer
├── whale_tracker.py     # ERC-20 whale movement tracker
├── alerts.py            # Telegram + Discord alert delivery
├── trading_signals.py   # Technical indicator signal generator
├── dashboard.py         # Streamlit dashboard
└── portfolio.py         # Multi-wallet portfolio tracker
tests/
├── test_monitor.py
├── test_analyzer.py
└── test_signals.py
examples/
├── basic_monitor.py
└── whale_alert_bot.py
agents/
└── sentinel.py          # All-in-one monitoring agent
```

## Why I Built This

In early 2026 I ape'd into two contracts that looked legit. First one had a hidden mint function that drained liquidity. Second one used `delegatecall` to a proxy that swapped the implementation after launch. Both times I was watching Etherscan by hand, refreshing pages like it was 2017.

Never again. ChainLens does the watching. If something smells wrong — an owner-gated mint, a suspicious `selfdestruct`, a whale moving 5M USDT at 3am — I know about it before the transaction confirms.

## License

MIT — do whatever you want with it. If it saves you from a rug, buy me a coffee.

## Contributing

PRs welcome. Open an issue first for big changes.

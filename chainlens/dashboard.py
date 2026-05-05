"""Streamlit dashboard with Plotly charts for ChainLens."""

import asyncio
import json
import os
from datetime import datetime, timezone

try:
    import streamlit as st
    import plotly.graph_objects as go
    import plotly.express as px
except ImportError:
    raise ImportError("Install with: pip install chainlens[dashboard]")

from chainlens.config import ChainLensConfig
from chainlens.trading_signals import TradingSignalGenerator, SignalType


# ── Page config ───────────────────────────────────────────────────

st.set_page_config(
    page_title="ChainLens Dashboard",
    page_icon="🔍",
    layout="wide",
)

st.title("🔍 ChainLens — EVM Blockchain Monitor")


# ── Sidebar ───────────────────────────────────────────────────────

with st.sidebar:
    st.header("Configuration")
    rpc_url = st.text_input("RPC URL", value=os.getenv("CHAINLENS_RPC_URL", ""))
    chain_id = st.number_input("Chain ID", value=1, min_value=1)
    whale_threshold = st.number_input("Whale threshold (ETH)", value=100.0, min_value=0.1)
    token_address = st.text_input("Token address to monitor", value="")
    st.divider()
    refresh_interval = st.slider("Refresh (seconds)", 5, 120, 30)


# ── Price chart tab ───────────────────────────────────────────────

tab_price, tab_whale, tab_signals, tab_audit = st.tabs(
    ["📈 Price / Signals", "🐋 Whale Tracker", "🎯 Signals", "🔎 Contract Audit"]
)

with tab_price:
    st.subheader("Price History & Moving Averages")

    # Demo data (replace with live feed in production)
    import random
    random.seed(42)
    demo_prices = [1800 + i * 2 + random.uniform(-20, 20) for i in range(100)]

    gen = TradingSignalGenerator(short_window=7, long_window=25)
    short_sma = gen.sma(demo_prices, 7)
    long_sma = gen.sma(demo_prices, 25)

    fig = go.Figure()
    fig.add_trace(go.Scatter(y=demo_prices, name="Price", line=dict(color="#3498DB")))
    fig.add_trace(go.Scatter(y=[None] * 6 + short_sma, name="SMA 7", line=dict(color="#E67E22")))
    fig.add_trace(go.Scatter(y=[None] * 24 + long_sma, name="SMA 25", line=dict(color="#2ECC71")))
    fig.update_layout(template="plotly_dark", height=500, xaxis_title="Block offset", yaxis_title="Price (USD)")
    st.plotly_chart(fig, use_container_width=True)

    # RSI subplot
    rsi_vals = gen.rsi(demo_prices)
    fig_rsi = go.Figure()
    fig_rsi.add_trace(go.Scatter(y=rsi_vals, name="RSI", line=dict(color="#9B59B6")))
    fig_rsi.add_hline(y=70, line_dash="dash", line_color="red", annotation_text="Overbought")
    fig_rsi.add_hline(y=30, line_dash="dash", line_color="green", annotation_text="Oversold")
    fig_rsi.update_layout(template="plotly_dark", height=250, yaxis_title="RSI")
    st.plotly_chart(fig_rsi, use_container_width=True)


with tab_whale:
    st.subheader("🐋 Recent Whale Movements")
    # Demo data
    whale_data = [
        {"Time": "2 min ago", "Token": "USDT", "Amount": "5,000,000", "From": "0xdead...beef", "To": "Binance", "Direction": "→ CEX"},
        {"Time": "15 min ago", "Token": "ETH", "Amount": "2,500", "From": "Whale 0xabcd", "To": "Uniswap", "Direction": "DEX swap"},
        {"Time": "1 hr ago", "Token": "USDC", "Amount": "1,200,000", "From": "Circle", "To": "0x1234...5678", "Direction": "Mint"},
    ]
    st.dataframe(whale_data, use_container_width=True)

    # Volume bar chart
    tokens = ["USDT", "ETH", "USDC", "WBTC", "DAI"]
    volumes = [5_000_000, 4_500_000, 1_200_000, 800_000, 300_000]
    fig_vol = px.bar(x=tokens, y=volumes, labels={"x": "Token", "y": "Volume (USD)"}, color=volumes, color_continuous_scale="Reds")
    fig_vol.update_layout(template="plotly_dark", height=350)
    st.plotly_chart(fig_vol, use_container_width=True)


with tab_signals:
    st.subheader("🎯 Active Trading Signals")
    signals = gen.generate("ETH/USD", demo_prices)
    if signals:
        for sig in signals:
            color = {"BUY": "🟢", "SELL": "🔴", "HOLD": "🟡", "ALERT": "🟠"}.get(sig.signal_type.value, "⚪")
            st.markdown(f"{color} **{sig.signal_type.value}** — confidence {sig.confidence:.0%} — {sig.reason}")
    else:
        st.info("No signals generated. Need more price data.")


with tab_audit:
    st.subheader("🔎 Contract Bytecode Audit")
    audit_addr = st.text_input("Contract address", value="", key="audit_addr")
    if audit_addr and st.button("Analyze"):
        st.info(f"Would analyze {audit_addr} via ContractAnalyzer (connect RPC first)")
        # In production: result = await analyzer.analyze(audit_addr)
        st.markdown("""
        **Demo output:**
        - Bytecode size: 12,847 bytes
        - Risk score: 45/100 (MEDIUM)
        - ⚠️ Uses delegatecall (proxy pattern)
        - ⚠️ Owner-gated mint function detected
        - Selectors: `transfer`, `approve`, `balanceOf`, `mint`, `owner`
        """)


# ── Footer ────────────────────────────────────────────────────────

st.divider()
st.caption("ChainLens v0.1.0 — Built because I got rugged twice.")

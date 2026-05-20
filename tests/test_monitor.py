"""Tests for the block monitor."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from chainlens.monitor import BlockMonitor
from chainlens.config import ChainLensConfig


@pytest.fixture
def config():
    return ChainLensConfig(rpc_url="http://localhost:8545", poll_interval=0.1)


@pytest.fixture
def monitor(config):
    return BlockMonitor(config)


class TestBlockMonitor:
    def test_init_defaults(self):
        m = BlockMonitor()
        assert m._running is False
        assert m._callbacks == []

    def test_on_block_registers_callback(self, monitor):
        called = []
        @monitor.on_block
        def handler(block):
            called.append(block)
        assert len(monitor._callbacks) == 1

    def test_reset_reconnect_delay(self, monitor):
        monitor._reconnect_delay = 30.0
        monitor._reset_reconnect_delay()
        assert monitor._reconnect_delay == 2.0

    def test_bump_reconnect_delay(self, monitor):
        monitor._reconnect_delay = 2.0
        monitor._bump_reconnect_delay()
        assert monitor._reconnect_delay == 4.0
        monitor._bump_reconnect_delay()
        assert monitor._reconnect_delay == 8.0

    def test_bump_reconnect_delay_caps_at_max(self, monitor):
        monitor._reconnect_delay = 120.0
        monitor._bump_reconnect_delay()
        assert monitor._reconnect_delay == 60.0

    @pytest.mark.asyncio
    async def test_notify_calls_callbacks(self, monitor):
        results = []
        @monitor.on_block
        async def handler(block):
            results.append(block)

        await monitor._notify({"number": "0x1"})
        assert len(results) == 1
        assert results[0]["number"] == "0x1"

    @pytest.mark.asyncio
    async def test_notify_handles_sync_callbacks(self, monitor):
        results = []
        @monitor.on_block
        def handler(block):
            results.append(block)

        await monitor._notify({"number": "0xa"})
        assert results == [{"number": "0xa"}]

"""Portfolio tracker — track ERC-20 + native balances across wallets."""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import aiohttp

from chainlens.config import ChainLensConfig

logger = logging.getLogger("chainlens.portfolio")

# Minimal ERC-20 ABI fragments
BALANCE_OF_SELECTOR = "0x70a08231"
DECIMALS_SELECTOR = "0x313ce567"
NAME_SELECTOR = "0x06fdde03"
SYMBOL_SELECTOR = "0x95d89b41"

# Well-known tokens (mainnet)
KNOWN_TOKENS = {
    "0xdac17f958d2ee523a2206206994597c13d831ec7": {"symbol": "USDT", "decimals": 6},
    "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48": {"symbol": "USDC", "decimals": 6},
    "0x6b175474e89094c44da98b954eedeac495271d0f": {"symbol": "DAI", "decimals": 18},
    "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2": {"symbol": "WETH", "decimals": 18},
    "0x2260fac5e5542a773aa44fbcfedf7c193bc2c599": {"symbol": "WBTC", "decimals": 8},
}


@dataclass
class TokenBalance:
    token_address: str
    symbol: str
    decimals: int
    raw_balance: int
    price_usd: Optional[float] = None

    @property
    def balance(self) -> float:
        return self.raw_balance / (10 ** self.decimals)

    @property
    def value_usd(self) -> Optional[float]:
        if self.price_usd is not None:
            return self.balance * self.price_usd
        return None


@dataclass
class WalletPortfolio:
    address: str
    native_balance_eth: float = 0.0
    tokens: list[TokenBalance] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def total_value_usd(self) -> Optional[float]:
        values = [t.value_usd for t in self.tokens if t.value_usd is not None]
        if not values:
            return None
        return sum(values)


class PortfolioTracker:
    """Fetches and tracks ERC-20 + native balances for given wallets."""

    def __init__(self, config: Optional[ChainLensConfig] = None, token_list: Optional[list[str]] = None):
        self.config = config or ChainLensConfig()
        self._session: Optional[aiohttp.ClientSession] = None
        self.tokens_to_track = [
            addr.lower() for addr in (token_list or list(KNOWN_TOKENS.keys()))
        ]

    async def _ensure_session(self):
        if not self._session:
            self._session = aiohttp.ClientSession()

    async def _rpc_call(self, method: str, params: list) -> dict:
        await self._ensure_session()
        payload = {"jsonrpc": "2.0", "method": method, "params": params, "id": 1}
        async with self._session.post(self.config.rpc_url, json=payload) as resp:
            data = await resp.json()
            return data

    async def _get_eth_balance(self, address: str) -> int:
        result = await self._rpc_call("eth_getBalance", [address, "latest"])
        return int(result.get("result", "0x0"), 16)

    async def _get_erc20_balance(self, token: str, wallet: str) -> int:
        padded = wallet[2:].lower().zfill(64)
        data = BALANCE_OF_SELECTOR + padded
        result = await self._rpc_call("eth_call", [{"to": token, "data": data}, "latest"])
        hex_val = result.get("result", "0x")
        return int(hex_val, 16) if hex_val and hex_val != "0x" else 0

    async def get_portfolio(self, wallet_address: str,
                            price_map: Optional[dict[str, float]] = None) -> WalletPortfolio:
        """Fetch full portfolio for a wallet."""
        wallet = wallet_address.lower()
        portfolio = WalletPortfolio(address=wallet)

        # Native balance
        raw_eth = await self._get_eth_balance(wallet)
        portfolio.native_balance_eth = raw_eth / 1e18
        logger.info("Wallet %s: %.4f ETH", wallet[:10], portfolio.native_balance_eth)

        # ERC-20 balances (concurrent)
        async def _fetch_token(token_addr: str) -> Optional[TokenBalance]:
            bal = await self._get_erc20_balance(token_addr, wallet)
            if bal == 0:
                return None
            info = KNOWN_TOKENS.get(token_addr, {})
            symbol = info.get("symbol", token_addr[:10])
            decimals = info.get("decimals", 18)
            price = (price_map or {}).get(token_addr)
            return TokenBalance(
                token_address=token_addr,
                symbol=symbol,
                decimals=decimals,
                raw_balance=bal,
                price_usd=price,
            )

        tasks = [_fetch_token(t) for t in self.tokens_to_track]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in results:
            if isinstance(r, TokenBalance):
                portfolio.tokens.append(r)

        portfolio.tokens.sort(key=lambda t: t.balance, reverse=True)
        logger.info("Portfolio: %d token balances fetched", len(portfolio.tokens))
        return portfolio

    async def close(self):
        if self._session:
            await self._session.close()

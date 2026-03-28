"""Contract bytecode analyzer — decompile, pattern-match, risk-score."""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Optional

import aiohttp

from chainlens.config import ChainLensConfig

logger = logging.getLogger("chainlens.analyzer")

# Known signatures (selector → human label)
KNOWN_SELECTORS = {
    "a9059cbb": "transfer(address,uint256)",
    "095ea7b3": "approve(address,uint256)",
    "23b872dd": "transferFrom(address,address,uint256)",
    "70a08231": "balanceOf(address)",
    "18160ddd": "totalSupply()",
    "313ce567": "decimals()",
    "06fdde03": "name()",
    "95d89b41": "symbol()",
    "a0712d68": "mint(uint256)",
    "40c10f19": "mint(address,uint256)",
    "8da5cb5b": "owner()",
    "715018a6": "renounceOwnership()",
    "f2fde38b": "transferOwnership(address)",
    "39509351": "increaseAllowance(address,uint256)",
    "a457c2d7": "decreaseAllowance(address,uint256)",
}

RISKY_PATTERNS = {
    "selfdestruct": "Contract can self-destruct",
    "delegatecall": "Uses delegatecall (proxy pattern — can be dangerous)",
    "tx.origin": "Uses tx.origin for auth (phishing risk)",
    "suicide": "Legacy self-destruct",
    "create2": "CREATE2 (factory pattern or upgradeable proxy)",
}


@dataclass
class AnalysisResult:
    address: str
    bytecode_size: int
    selectors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    risk_score: float = 0.0  # 0 = safe, 100 = extreme risk

    @property
    def risk_label(self) -> str:
        if self.risk_score >= 80:
            return "CRITICAL"
        if self.risk_score >= 50:
            return "HIGH"
        if self.risk_score >= 25:
            return "MEDIUM"
        return "LOW"


class ContractAnalyzer:
    """Fetches and analyzes EVM contract bytecode."""

    def __init__(self, config: Optional[ChainLensConfig] = None):
        self.config = config or ChainLensConfig()
        self._session: Optional[aiohttp.ClientSession] = None

    async def _ensure_session(self):
        if not self._session:
            self._session = aiohttp.ClientSession()

    async def _get_code(self, address: str) -> str:
        await self._ensure_session()
        payload = {
            "jsonrpc": "2.0",
            "method": "eth_getCode",
            "params": [address, "latest"],
            "id": 1,
        }
        async with self._session.post(self.config.rpc_url, json=payload) as resp:
            data = await resp.json()
            return data.get("result", "0x")

    async def analyze(self, address: str) -> AnalysisResult:
        """Analyze a contract at *address* and return an AnalysisResult."""
        code = await self._get_code(address)
        result = AnalysisResult(address=address, bytecode_size=len(code) // 2 - 1)

        if code in ("0x", "0x0"):
            result.warnings.append("EOA or empty — no contract deployed")
            return result

        # Extract 4-byte selectors (PUSH4 opcodes: 0x63 + 4 bytes)
        raw = bytes.fromhex(code[2:])
        i = 0
        selectors = set()
        while i < len(raw) - 4:
            if raw[i] == 0x63:
                sel = raw[i + 1 : i + 5].hex()
                if sel in KNOWN_SELECTORS:
                    selectors.add(sel)
            i += 1
        result.selectors = sorted(selectors)

        # Risky opcodes / patterns
        code_lower = code.lower()
        for pattern, warning in RISKY_PATTERNS.items():
            if pattern in code_lower:
                result.warnings.append(warning)

        # Heuristic risk scoring
        score = 0
        if result.bytecode_size < 100:
            score += 30  # suspiciously small
            result.warnings.append("Very small bytecode — possible minimal proxy or stub")
        if "selfdestruct" in code_lower or "suicide" in code_lower:
            score += 40
        if "delegatecall" in code_lower:
            score += 20
        if "tx.origin" in code_lower:
            score += 25
        if "095ea7b3" in selectors and "a9059cbb" not in selectors:
            score += 10  # has approve but no transfer
        if "40c10f19" in selectors or "a0712d68" in selectors:
            if "8da5cb5b" in selectors:
                score += 15  # owner-gated mint

        result.risk_score = min(score, 100)
        logger.info("Analyzed %s — %d bytes, %d selectors, risk %s (%d)",
                     address, result.bytecode_size, len(result.selectors),
                     result.risk_label, result.risk_score)
        return result

    async def close(self):
        if self._session:
            await self._session.close()

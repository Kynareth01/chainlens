"""Tests for the contract analyzer."""

import pytest

from chainlens.analyzer import ContractAnalyzer, AnalysisResult, KNOWN_SELECTORS


class TestAnalysisResult:
    def test_risk_label_critical(self):
        r = AnalysisResult(address="0x0", bytecode_size=100, risk_score=85)
        assert r.risk_label == "CRITICAL"

    def test_risk_label_high(self):
        r = AnalysisResult(address="0x0", bytecode_size=100, risk_score=60)
        assert r.risk_label == "HIGH"

    def test_risk_label_medium(self):
        r = AnalysisResult(address="0x0", bytecode_size=100, risk_score=30)
        assert r.risk_label == "MEDIUM"

    def test_risk_label_low(self):
        r = AnalysisResult(address="0x0", bytecode_size=100, risk_score=10)
        assert r.risk_label == "LOW"


class TestKnownSelectors:
    def test_transfer_selector(self):
        assert KNOWN_SELECTORS["a9059cbb"] == "transfer(address,uint256)"

    def test_approve_selector(self):
        assert KNOWN_SELECTORS["095ea7b3"] == "approve(address,uint256)"

    def test_has_mint_selectors(self):
        assert "a0712d68" in KNOWN_SELECTORS
        assert "40c10f19" in KNOWN_SELECTORS

    def test_has_owner_selector(self):
        assert KNOWN_SELECTORS["8da5cb5b"] == "owner()"


class TestContractAnalyzer:
    def test_init(self):
        analyzer = ContractAnalyzer()
        assert analyzer.config is not None

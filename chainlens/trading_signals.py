"""Trading signal generator — technical indicators + on-chain heuristics."""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

logger = logging.getLogger("chainlens.trading_signals")


class SignalType(Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    ALERT = "ALERT"


@dataclass
class Signal:
    token: str
    signal_type: SignalType
    confidence: float  # 0.0 – 1.0
    reason: str
    price: Optional[float] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class TradingSignalGenerator:
    """Generates trading signals from price data and on-chain metrics."""

    def __init__(self, short_window: int = 7, long_window: int = 25):
        self.short_window = short_window
        self.long_window = long_window

    # ── Technical indicators ──────────────────────────────────────

    @staticmethod
    def sma(prices: list[float], window: int) -> list[float]:
        """Simple Moving Average."""
        if len(prices) < window:
            return []
        result = []
        for i in range(window - 1, len(prices)):
            avg = sum(prices[i - window + 1 : i + 1]) / window
            result.append(avg)
        return result

    @staticmethod
    def ema(prices: list[float], window: int) -> list[float]:
        """Exponential Moving Average."""
        if len(prices) < window:
            return []
        k = 2 / (window + 1)
        result = [sum(prices[:window]) / window]
        for price in prices[window:]:
            result.append(price * k + result[-1] * (1 - k))
        return result

    @staticmethod
    def rsi(prices: list[float], period: int = 14) -> list[float]:
        """Relative Strength Index."""
        if len(prices) < period + 1:
            return []
        deltas = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
        gains = [d if d > 0 else 0 for d in deltas]
        losses = [-d if d < 0 else 0 for d in deltas]

        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period

        rsi_values = []
        for i in range(period, len(deltas)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period
            if avg_loss == 0:
                rsi_values.append(100.0)
            else:
                rs = avg_gain / avg_loss
                rsi_values.append(100 - 100 / (1 + rs))
        return rsi_values

    @staticmethod
    def bollinger_bands(prices: list[float], window: int = 20, num_std: float = 2.0):
        """Returns (upper, middle, lower) bands."""
        if len(prices) < window:
            return [], [], []
        middles = []
        uppers = []
        lowers = []
        for i in range(window - 1, len(prices)):
            window_prices = prices[i - window + 1 : i + 1]
            mean = sum(window_prices) / window
            variance = sum((p - mean) ** 2 for p in window_prices) / window
            std = variance ** 0.5
            middles.append(mean)
            uppers.append(mean + num_std * std)
            lowers.append(mean - num_std * std)
        return uppers, middles, lowers

    # ── Signal generation ─────────────────────────────────────────

    def generate(self, token: str, prices: list[float],
                 volume_24h: Optional[float] = None,
                 whale_activity: bool = False) -> list[Signal]:
        """Generate signals for a token given price history."""
        signals: list[Signal] = []

        if len(prices) < self.long_window + 5:
            logger.debug("Not enough data for %s (%d points)", token, len(prices))
            return signals

        current_price = prices[-1]

        # 1. SMA crossover
        short_sma = self.sma(prices, self.short_window)
        long_sma = self.sma(prices, self.long_window)
        if short_sma and long_sma:
            if short_sma[-1] > long_sma[-1] and short_sma[-2] <= long_sma[-2]:
                signals.append(Signal(
                    token=token, signal_type=SignalType.BUY,
                    confidence=0.65, price=current_price,
                    reason=f"SMA{self.short_window} crossed above SMA{self.long_window} (golden cross)",
                ))
            elif short_sma[-1] < long_sma[-1] and short_sma[-2] >= long_sma[-2]:
                signals.append(Signal(
                    token=token, signal_type=SignalType.SELL,
                    confidence=0.65, price=current_price,
                    reason=f"SMA{self.short_window} crossed below SMA{self.long_window} (death cross)",
                ))

        # 2. RSI
        rsi_vals = self.rsi(prices)
        if rsi_vals:
            latest_rsi = rsi_vals[-1]
            if latest_rsi < 30:
                signals.append(Signal(
                    token=token, signal_type=SignalType.BUY,
                    confidence=0.7, price=current_price,
                    reason=f"RSI oversold at {latest_rsi:.1f}",
                ))
            elif latest_rsi > 70:
                signals.append(Signal(
                    token=token, signal_type=SignalType.SELL,
                    confidence=0.7, price=current_price,
                    reason=f"RSI overbought at {latest_rsi:.1f}",
                ))

        # 3. Bollinger Bands
        uppers, middles, lowers = self.bollinger_bands(prices)
        if lowers and current_price < lowers[-1]:
            signals.append(Signal(
                token=token, signal_type=SignalType.BUY,
                confidence=0.6, price=current_price,
                reason="Price below lower Bollinger Band",
            ))
        elif uppers and current_price > uppers[-1]:
            signals.append(Signal(
                token=token, signal_type=SignalType.SELL,
                confidence=0.6, price=current_price,
                reason="Price above upper Bollinger Band",
            ))

        # 4. Whale activity override
        if whale_activity:
            for s in signals:
                s.confidence = min(s.confidence + 0.15, 1.0)
                s.reason += " + whale activity detected"

        # Deduplicate: keep strongest signal per type
        best: dict[SignalType, Signal] = {}
        for s in signals:
            if s.signal_type not in best or s.confidence > best[s.signal_type].confidence:
                best[s.signal_type] = s
        return list(best.values())

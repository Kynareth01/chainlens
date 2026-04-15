"""Alert delivery — Telegram and Discord webhooks."""

import asyncio
import logging
from dataclasses import dataclass
from typing import Optional

import aiohttp

from chainlens.config import ChainLensConfig

logger = logging.getLogger("chainlens.alerts")


@dataclass
class Alert:
    """A single alert message."""
    title: str
    body: str
    severity: str = "info"  # info, warning, critical
    source: str = ""


class AlertManager:
    """Dispatches alerts to Telegram and/or Discord."""

    def __init__(self, config: Optional[ChainLensConfig] = None):
        self.config = config or ChainLensConfig()
        self._session: Optional[aiohttp.ClientSession] = None

    async def _ensure_session(self):
        if not self._session:
            self._session = aiohttp.ClientSession()

    # ── Telegram ──────────────────────────────────────────────────

    def _format_telegram(self, alert: Alert) -> str:
        icon = {"info": "ℹ️", "warning": "⚠️", "critical": "🚨"}.get(alert.severity, "📢")
        lines = [f"{icon} *{alert.title}*", ""]
        if alert.source:
            lines.append(f"Source: `{alert.source}`")
        lines.append(alert.body)
        return "\n".join(lines)

    async def _send_telegram(self, alert: Alert):
        if not self.config.telegram_bot_token or not self.config.telegram_chat_id:
            logger.debug("Telegram not configured — skipping")
            return

        await self._ensure_session()
        url = f"https://api.telegram.org/bot{self.config.telegram_bot_token}/sendMessage"
        payload = {
            "chat_id": self.config.telegram_chat_id,
            "text": self._format_telegram(alert),
            "parse_mode": "Markdown",
            "disable_web_page_preview": True,
        }
        try:
            async with self._session.post(url, json=payload) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    logger.warning("Telegram %d: %s", resp.status, body[:200])
                else:
                    logger.debug("Telegram sent OK")
        except Exception as exc:
            logger.error("Telegram send failed: %s", exc)

    # ── Discord ───────────────────────────────────────────────────

    def _format_discord(self, alert: Alert) -> dict:
        color = {"info": 0x3498DB, "warning": 0xF39C12, "critical": 0xE74C3C}.get(alert.severity, 0x95A5A6)
        fields = []
        if alert.source:
            fields.append({"name": "Source", "value": f"`{alert.source}`", "inline": True})
        fields.append({"name": "Details", "value": alert.body[:1024], "inline": False})
        return {
            "embeds": [{
                "title": alert.title,
                "color": color,
                "fields": fields,
            }]
        }

    async def _send_discord(self, alert: Alert):
        if not self.config.discord_webhook_url:
            logger.debug("Discord not configured — skipping")
            return

        await self._ensure_session()
        try:
            async with self._session.post(self.config.discord_webhook_url, json=self._format_discord(alert)) as resp:
                if resp.status not in (200, 204):
                    body = await resp.text()
                    logger.warning("Discord %d: %s", resp.status, body[:200])
                else:
                    logger.debug("Discord sent OK")
        except Exception as exc:
            logger.error("Discord send failed: %s", exc)

    # ── Public API ────────────────────────────────────────────────

    async def send(self, alert: Alert):
        """Send alert to all configured channels."""
        logger.info("Alert [%s]: %s", alert.severity, alert.title)
        await asyncio.gather(
            self._send_telegram(alert),
            self._send_discord(alert),
            return_exceptions=True,
        )

    def send_sync(self, alert: Alert):
        """Blocking helper."""
        loop = asyncio.new_event_loop()
        loop.run_until_complete(self.send(alert))
        loop.close()

    async def close(self):
        if self._session:
            await self._session.close()

from __future__ import annotations

import logging
from dataclasses import dataclass


@dataclass(slots=True)
class AlertManager:
    enabled: bool = False
    logger: logging.Logger = logging.getLogger("bot.alerts")

    async def alert(self, event_type: str, message: str, **fields: object) -> None:
        payload = {"event": event_type, "message": message, **fields}
        if self.enabled:
            self.logger.warning("alert", extra={"event_payload": payload})
        else:
            self.logger.info("alert_suppressed", extra={"event_payload": payload})


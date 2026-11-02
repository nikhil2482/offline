"""ASGI entry point: uvicorn offline.main:app"""

from offline.api import create_app
from offline.config import Settings
from offline.services import build

_services = build(Settings())
app = create_app(
    _services.answerer,
    _services.audit,
    _services.users,
    _services.limiter,
    _services.settings.mode.value,
)

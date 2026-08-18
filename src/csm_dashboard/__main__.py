from __future__ import annotations

import uvicorn

from csm_dashboard.config import load_settings
from csm_dashboard.logging_setup import configure_logging


def main() -> None:
    configure_logging()
    settings = load_settings()
    uvicorn.run(
        "csm_dashboard.web.app:create_app",
        factory=True,
        host=settings.host,
        port=settings.port,
        reload=False,
    )


if __name__ == "__main__":
    main()

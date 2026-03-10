"""
Run the FastAPI app with: python main.py

This keeps the real application in `app/main.py` while providing a simple entrypoint.
"""

from __future__ import annotations

import uvicorn

from app.config import settings


def main() -> None:
    uvicorn.run(
        "app.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG,
    )


if __name__ == "__main__":
    main()

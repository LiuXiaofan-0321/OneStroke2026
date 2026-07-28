"""Start the authenticated OneStroke model HTTP service."""

from __future__ import annotations

import argparse
import logging
import os

from onestroke_model.http_api import ServiceSettings, create_app


def main() -> None:
    parser = argparse.ArgumentParser(description="Start the OneStroke course-practice HTTP API.")
    parser.add_argument("--host", default=os.environ.get("ONESTROKE_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("ONESTROKE_PORT", "8000")))
    parser.add_argument("--log-level", default=os.environ.get("ONESTROKE_LOG_LEVEL", "info"))
    args = parser.parse_args()

    try:
        import uvicorn
    except ImportError as exc:  # pragma: no cover - exercised by deployment setup
        raise SystemExit("Install the service extra with: python -m pip install -e '.[serve]'") from exc

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    settings = ServiceSettings.from_environment(require_api_key=True)
    uvicorn.run(create_app(settings), host=args.host, port=args.port, log_level=args.log_level)


if __name__ == "__main__":
    main()

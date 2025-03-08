"""
Main application for the Edge-AI backend
"""

# -----------------------------------------------------------------------------
# FastAPI for backend API development
# -----------------------------------------------------------------------------
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# -----------------------------------------------------------------------------
# Structured Logging Configuration using structlog
# -----------------------------------------------------------------------------
import structlog, sys, logging

logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="%(message)s"
)

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.dev.ConsoleRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)
logger = structlog.get_logger()

# -----------------------------------------------------------------------------
# FastAPI Application Setup
# -----------------------------------------------------------------------------
class MainApp:
    """
    Encapsulates FastAPI application setup and routes.
    """
    def __init__(self) -> None:
        self.app = FastAPI()
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        self._setup_routes()

    def _setup_routes(self) -> None:
        @self.app.get("/")
        def _default():
            """
            Default chat endpoint.
            """
            return {"response": "Edge-AI Backend is running"}


# -----------------------------------------------------------------------------
# Entry Point
# -----------------------------------------------------------------------------
app_instance = MainApp()
app = app_instance.app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=5000, reload=True)
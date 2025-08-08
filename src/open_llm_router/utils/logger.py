import logging
import time
from typing import Dict, Any, Optional
from contextlib import contextmanager
import httpx

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("llm_router")


class ProxyLogger:
    def __init__(self, name: str = "llm_router"):
        self.logger = logging.getLogger(name)

    def info(self, message: str, **kwargs):
        self.logger.info(message, **kwargs)

    def debug(self, message: str, **kwargs):
        self.logger.debug(message, **kwargs)

    def warning(self, message: str, **kwargs):
        self.logger.warning(message, **kwargs)

    def error(self, message: str, **kwargs):
        self.logger.error(message, **kwargs)

    def log_request(self, provider: str, model: str, url: str, stream: bool = False):
        """Log outgoing request to upstream provider"""
        self.info(
            f"→ {provider.upper()}: {model} {'(streaming)' if stream else ''} -> {url}"
        )

    def log_response(
        self, provider: str, status_code: int, duration_ms: float, model: str
    ):
        """Log response from upstream provider with timing and status"""
        duration_str = f"{duration_ms:.0f}ms"
        status_emoji = "✓" if 200 <= status_code < 300 else "✗"
        self.info(
            f"← {provider.upper()}: {status_emoji} {status_code} in {duration_str} for {model}"
        )

    @contextmanager
    def time_request(self, provider: str, model: str, url: str, stream: bool = False):
        """Context manager to time and log requests"""
        start_time = time.time()
        self.log_request(provider, model, url, stream)

        try:
            yield
        finally:
            # This will be called in the calling code after the response is received
            pass

    def time_and_log_response(
        self, provider: str, model: str, response: httpx.Response, start_time: float
    ):
        """Log response timing after receiving response"""
        duration_ms = (time.time() - start_time) * 1000
        self.log_response(provider, response.status_code, duration_ms, model)


# Create global logger instance
proxy_logger = ProxyLogger()

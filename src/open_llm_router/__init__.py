"""
OpenWebUI Service Manager

A complete service management solution for running Open-WebUI with PostgreSQL database
and multi-provider LLM router.
"""

__version__ = "1.0.0"
__author__ = "OpenWebUI Service Manager"

from .llm_router import app
from .pg_init import PostgresInitializer

__all__ = ["app", "PostgresInitializer"]

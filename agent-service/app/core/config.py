"""Agent Service Configuration"""

import os
from typing import Optional
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment"""

    # Application
    app_name: str = "Shopping Agent"
    debug: bool = True
    host: str = "0.0.0.0"
    port: int = 8000

    # Additional host/port settings from .env
    agent_host: Optional[str] = None
    agent_port: Optional[int] = None
    merchant_host: Optional[str] = None
    merchant_port: Optional[int] = None

    # Merchant Configuration
    merchant_base_url: str = "http://localhost:8001"
    merchant_name: str = "Mock Merchant Store"

    # TAP Configuration
    tap_agent_id: str = "shopping-agent-001"
    tap_agent_keyid: str = "https://registry.visa.com/agents/shopping-agent-001"
    tap_private_key_path: Optional[str] = None
    tap_private_key: Optional[str] = None  # Can also be inline
    tap_agent_public_key_path: Optional[str] = None
    tap_agent_public_key: Optional[str] = None

    # Visa MCP Configuration
    mcp_base_url: str = "https://sandbox.mcp.visa.com"
    vic_api_key: Optional[str] = None
    vic_api_key_ss: Optional[str] = None
    vts_api_key: Optional[str] = None
    vts_api_key_ss: Optional[str] = None
    mle_server_cert: Optional[str] = None
    mle_private_key: Optional[str] = None
    key_id: Optional[str] = None
    external_client_id: Optional[str] = None
    external_app_id: Optional[str] = None
    user_signing_private_key: Optional[str] = None

    # LLM Configuration
    anthropic_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    llm_model: str = "claude-3-sonnet-20240229"

    # Auth callback URL (for Passkey flows)
    auth_callback_url: str = "http://localhost:8000/api/auth/callback"

    class Config:
        env_file = "../config/.env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    def get_tap_private_key(self) -> Optional[str]:
        """Get TAP private key from file or inline"""
        if self.tap_private_key:
            return self.tap_private_key

        if self.tap_private_key_path and os.path.exists(self.tap_private_key_path):
            with open(self.tap_private_key_path, "r") as f:
                return f.read()

        return None

    @property
    def visa_credentials_configured(self) -> bool:
        """Check if Visa credentials are configured"""
        return all([
            self.vic_api_key,
            self.vic_api_key_ss,
            self.vts_api_key,
            self.vts_api_key_ss,
        ])


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


settings = get_settings()

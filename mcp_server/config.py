from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class MCPSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    db_path: Path = Path("warehouse/shelfpulse.duckdb")
    mcp_host: str = "127.0.0.1"
    mcp_port: int = 8001

settings = MCPSettings()
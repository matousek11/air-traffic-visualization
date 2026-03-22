import os
from dotenv import load_dotenv

class Env:
    def __init__(self) -> None:
        load_dotenv(override=False)

    def req(self, key: str) -> str:
        value = os.getenv(key)
        if value is None:
            raise KeyError(f"Missing required env var: {key}")
        return value

    def str(self, key: str, default: str | None = None) -> str | None:
        return os.getenv(key, default)

    def int(self, key: str, default: int | None = None) -> int | None:
        value = os.getenv(key)
        if value is None:
            return default
        try:
            return int(value)
        except ValueError as e:
            raise ValueError(
                f"Environment variable {key} must be an integer, got '{value}'"
            ) from e
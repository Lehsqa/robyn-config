from pydantic import BaseModel

from .core import ROOT_PATH


class Settings(BaseModel):
    driver: str = "sqlite+aiosqlite"
    host: str = "database"
    port: int = 5432
    user: str = "sqlite"
    password: str = "sqlite"
    name: str = "robyn_backend_template"

    @property
    def url(self) -> str:
        # SQLite stays the default for dev/test simplicity.
        if "sqlite" in self.driver:
            return f"{self.driver}:///{ROOT_PATH / self.name}.db"
        return (
            f"{self.driver}://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.name}"
        )

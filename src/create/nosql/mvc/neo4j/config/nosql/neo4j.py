from pydantic import BaseModel


class Settings(BaseModel):
    uri: str = "neo4j://neo4j:7687"
    user: str = "neo4j"
    password: str = "app-password"
    database: str = "neo4j"

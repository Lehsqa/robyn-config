from .app import app


@app.task
def example_task(value: str) -> str:
    return value


@app.task
def periodic_job() -> None:
    return None

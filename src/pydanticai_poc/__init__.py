"""Local read-only research agent."""


def main() -> None:
    import uvicorn

    uvicorn.run("pydanticai_poc.app:app", host="127.0.0.1", port=8000, workers=1)

import uvicorn

from .config import load_config


def main() -> None:
    config = load_config()
    uvicorn.run(
        "pyapi.main:app",
        host=config.host,
        port=config.port,
        reload=True,
    )


if __name__ == "__main__":
    main()

import uvicorn
from prometheus_client import start_http_server

from .settings import settings

if __name__ == "__main__":
    if settings.prometheus_enabled:
        start_http_server(settings.prometheus_port)

    uvicorn.run(
        "llama_deploy.apiserver.app:app",
        host=settings.host,
        port=settings.port,
    )

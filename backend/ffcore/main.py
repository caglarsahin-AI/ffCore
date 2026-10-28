from contextlib import asynccontextmanager

from fastapi import FastAPI

from ffcore.core.audit import ensure_audit_partitions
from ffcore.core.errors import install_error_handlers


@asynccontextmanager
async def lifespan(_: FastAPI):
    # The schema comes from the migrate service; this only adds missing monthly partitions.
    await ensure_audit_partitions(2)
    yield


app = FastAPI(title="FFCore", lifespan=lifespan)
install_error_handlers(app)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}

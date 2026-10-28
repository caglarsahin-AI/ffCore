from fastapi import FastAPI

from ffcore.core.errors import install_error_handlers

app = FastAPI(title="FFCore")
install_error_handlers(app)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}

import time

from fastapi import FastAPI, Request

from app_shared import logger
from routes_auth import router as auth_router
from routes_catalog import router as catalog_router
from routes_users import router as users_router


app = FastAPI(title="Recc Engine API")


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time
    logger.info(
        "path %s | method %s | duration %.4fs | status %d",
        request.url.path,
        request.method,
        duration,
        response.status_code,
    )
    return response


app.include_router(auth_router)
app.include_router(catalog_router)
app.include_router(users_router)

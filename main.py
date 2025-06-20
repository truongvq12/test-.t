import os
from contextlib import asynccontextmanager

import fastapi.openapi.utils as fu
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi_csrf_jinja.middleware import FastAPICSRFJinjaMiddleware
from pydantic import ValidationError

from api.base import api_v1_router
from core.config import dev_origins, settings
from core.constants import CSRF_COOKIE_NAME, CSRF_HEADER_NAME
from core.database import close_database, connect_to_database
from core.exception_handlers import exception_handler, exception_validation_handler
from core.exceptions import AiSummarizerBadRequestException
from core.log import logger
from core.messages import setup_message_util
from schemas.base import ValidationErrorResponse
from services.azure_storage_service import close_azure_service, setup_azure_service
from web.base import api_router as web_app_router
from web.errors.route_errors import index_error


def include_router(app: FastAPI):
    app.include_router(api_v1_router)
    app.include_router(web_app_router)


def configure_static(app: FastAPI):
    app.mount("/static", StaticFiles(directory="static"), name="static")
    app.mount("/js", StaticFiles(directory="src/resources/js"), name="js")
    app.mount("/css", StaticFiles(directory="src/resources/css"), name="css")


def configure_middleware(app: FastAPI):
    if settings.is_local:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=dev_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    else:
        app.add_middleware(
            FastAPICSRFJinjaMiddleware,
            secret=settings.APP_KEY,
            cookie_name=CSRF_COOKIE_NAME,
            header_name=CSRF_HEADER_NAME,
        )


@asynccontextmanager
async def lifespan(_):
    # Startup
    await connect_to_database()
    await setup_message_util()
    setup_azure_service()

    yield
    # Shutdown
    await close_database()
    close_azure_service()
    logger.info("Application STOP")


def start_application():
    logger.info("Application START")
    app = FastAPI(lifespan=lifespan, title=settings.APP_NAME, version=settings.APP_VER)
    include_router(app)
    configure_static(app)
    configure_middleware(app)
    return app


app = start_application()


# Handle favicon
@app.get("/favicon.ico")
async def favicon():
    file_name = "favicon.png"
    file_path = os.path.join(app.root_path, "static/images", file_name)
    return FileResponse(
        path=file_path,
        headers={"Content-Disposition": "attachment; filename=" + file_name},
    )


# Handle all exception
@app.exception_handler(Exception)
async def exception_callback(request: Request, exc: Exception):
    return await exception_handler(request, exc, index_error)


# Handle validation error
@app.exception_handler(ValidationError)
@app.exception_handler(RequestValidationError)
def exception_validation_callback(request: Request, exc: Exception):
    return exception_validation_handler(request, exc)


# Handle 400 error
@app.exception_handler(400)
def custom_400_handler(_, exc: Exception):
    raise AiSummarizerBadRequestException(detail=[exc.detail])


# Override fastapi 422 schema
fu.validation_error_response_definition = ValidationErrorResponse.model_json_schema()

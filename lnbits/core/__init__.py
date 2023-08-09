from fastapi import APIRouter

from .views.admin_api import *  # noqa: F403
from .views.api import *  # noqa: F403
from .views.generic import *  # noqa: F403
from .views.public_api import *  # noqa: F403

core_app: APIRouter = APIRouter()


def init_core_routers(app):
    app.include_router(generic_router)  # noqa: F405
    app.include_router(public_router)  # noqa: F405
    app.include_router(api_router)  # noqa: F405
    app.include_router(admin_router)  # noqa: F405

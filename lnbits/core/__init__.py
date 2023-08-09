from fastapi import APIRouter

from .db import core_app_extra, db  # noqa: F401
from .views.admin_api import admin_router
from .views.api import api_router

# this compat is needed for usermanager extension
from .views.generic import update_user_extension  # noqa: F401
from .views.generic import generic_router
from .views.public_api import public_router

# backwards compatibility for extensions
core_app: APIRouter = APIRouter()


def init_core_routers(app):
    app.include_router(core_app)
    app.include_router(generic_router)
    app.include_router(public_router)
    app.include_router(api_router)
    app.include_router(admin_router)

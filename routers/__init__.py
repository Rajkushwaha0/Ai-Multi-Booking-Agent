from fastapi import APIRouter
from routers.v1 import v1_router

# ------------------------------------------------------------------------------
# Root API router — mounts all versioned routers.
# main.py includes this single router with no prefix.
#
# To add v2:
#   1. Create routers/v2/__init__.py with a v2_router
#   2. Import and mount it below — zero changes needed in main.py
# ------------------------------------------------------------------------------

api_router = APIRouter()

api_router.include_router(v1_router, prefix="/api/v1")

# Future versions — add here when ready:
# from routers.v2 import v2_router
# api_router.include_router(v2_router, prefix="/api/v2")

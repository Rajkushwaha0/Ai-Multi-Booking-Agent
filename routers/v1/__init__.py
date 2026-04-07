from fastapi import APIRouter

# ------------------------------------------------------------------------------
# V1 router — collects all v1 route modules into one router.
# main.py mounts this with prefix="/api/v1".
#
# To add a new v1 route:
#   1. Create routers/v1/your_module.py with an APIRouter
#   2. Import it below and call v1_router.include_router(...)
# ------------------------------------------------------------------------------

v1_router = APIRouter()

# Uncomment each line as the corresponding router module is implemented:
# from routers.v1 import chat, movie, cab, doctor, restaurant, payment

# v1_router.include_router(chat.router,       prefix="/chat",        tags=["Chat"])
# v1_router.include_router(movie.router,      prefix="/movies",      tags=["Movies"])
# v1_router.include_router(cab.router,        prefix="/cabs",        tags=["Cabs"])
# v1_router.include_router(doctor.router,     prefix="/doctors",     tags=["Doctors"])
# v1_router.include_router(restaurant.router, prefix="/restaurants", tags=["Restaurants"])
# v1_router.include_router(payment.router,    prefix="/payments",    tags=["Payments"])

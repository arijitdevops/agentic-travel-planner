from fastapi import APIRouter

from app.api import bookings, health, inventory, trips, users

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(users.router)
api_router.include_router(inventory.router)
api_router.include_router(trips.router)
api_router.include_router(bookings.router)

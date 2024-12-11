# main.py
from fastapi import FastAPI
from routers import availability, booking
from config.settings import Settings
import uvicorn

settings = Settings()

app = FastAPI(
    title=settings.app_name,
    description="Sistema de automatización para búsqueda y reserva de estacionamientos",
    debug=settings.debug
)

# Incluir routers
app.include_router(
    availability.router,
    prefix="/api/v1/availability",
    tags=["availability"]
)

app.include_router(
    booking.router,
    prefix="/api/v1/booking",
    tags=["booking"]
)

@app.get("/")
async def root():
    return {
        "app_name": settings.app_name,
        "version": "1.0.0",
        "status": "running"
    }

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=settings.debug)
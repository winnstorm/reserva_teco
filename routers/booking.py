from fastapi import APIRouter, HTTPException
from models.schemas import BookingRequest, BookingResponse
from services.booking_service import BookingService

router = APIRouter()
service = BookingService()

@router.post("/reserve", response_model=BookingResponse)
async def make_reservation(request: BookingRequest):
    try:
        return await service.make_reservation(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
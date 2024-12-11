from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class SearchRequest(BaseModel):
    booking_type: str  # "parking" o "desk"
    date: str  # formato: "DD/MM/YYYY"
    start_time: Optional[str] = "09:00"
    end_time: Optional[str] = "18:00"
    building: str

class AvailableSlot(BaseModel):
    space_id: str
    space_name: str
    available_slots: List[dict]

class BookingRequest(BaseModel):
    title: str
    space_id: str
    date: str
    start_time: str
    end_time: str
    location_id: str = "973"
    building_id: str = "965"
    floor_id: str = "3311"
    base_type: str = "4"

class BookingResponse(BaseModel):
    status: str
    message: str
    booking_url: Optional[str]
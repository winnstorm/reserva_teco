from fastapi import APIRouter, HTTPException
from typing import List, Optional
from models.schemas import SearchRequest, AvailableSlot
from services.availability_service import AvailabilityService
from services.queue_service import QueueService

router = APIRouter()
service = AvailabilityService()

@router.post("/search")
async def search_availability(request: SearchRequest):
    try:
        queue_service = QueueService()
        task_id = await queue_service.add_task("search", request.dict())
        return {"task_id": task_id, "message": "Task created successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/task/{task_id}")
async def get_task_status(task_id: str):
    try:
        queue_service = QueueService()
        result = await queue_service.get_task_status(task_id)
        if not result:
            raise HTTPException(status_code=404, detail="Task not found")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
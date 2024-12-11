from queue import Queue
from threading import Thread
import uuid
from datetime import datetime
from sqlalchemy.orm import Session
from models.database import Task, SessionLocal
import asyncio
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from services.availability_service import AvailabilityService
from services.booking_service import BookingService

class QueueService:
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        # Solo inicializar una vez
        if not self._initialized:
            self.task_queue = Queue()
            self.is_running = True
            # Crear el loop antes de iniciar el thread
            self.loop = asyncio.new_event_loop()
            self.executor = ThreadPoolExecutor(max_workers=1)
            self.worker_thread = Thread(target=self._process_queue)
            self.worker_thread.daemon = True
            self.worker_thread.start()
            self._initialized = True

    def _process_queue(self):
        """Thread principal para procesar la cola"""
        try:
            asyncio.set_event_loop(self.loop)
            while self.is_running:
                try:
                    if not self.task_queue.empty():
                        task = self.task_queue.get()
                        # Ejecutar la tarea asíncrona en el loop de eventos
                        self.loop.run_until_complete(self._process_task(task))
                        self.task_queue.task_done()
                except Exception as e:
                    logging.error(f"Error processing task: {str(e)}")
        except Exception as e:
            logging.error(f"Fatal error in queue processing: {str(e)}")

    async def _process_task(self, task):
        """Procesa una tarea individual"""
        db = SessionLocal()
        try:
            # Actualizar estado a PROCESSING
            db_task = db.query(Task).filter(Task.task_id == task["task_id"]).first()
            if db_task:
                db_task.status = "PROCESSING"
                db.commit()

                # Ejecutar la tarea en un executor para permitir operaciones bloqueantes
                result = await self._execute_task(task)

                # Actualizar resultado
                db_task.status = "COMPLETED"
                db_task.result = result
                db_task.completed_at = datetime.utcnow()
            else:
                logging.error(f"Task {task['task_id']} not found in database")
                
        except Exception as e:
            logging.error(f"Error in task {task['task_id']}: {str(e)}")
            if db_task:
                db_task.status = "FAILED"
                db_task.error = str(e)
                db_task.completed_at = datetime.utcnow()
        finally:
            db.commit()
            db.close()

    async def _execute_task(self, task):
        """Ejecuta la tarea específica basada en el tipo"""
        try:
            if task["request_type"] == "search":
                service = AvailabilityService()
                # Ejecutar la búsqueda en un thread separado
                return await self.loop.run_in_executor(
                    self.executor,
                    service.search_available_slots_sync,  # Versión sincrónica del método
                    task["request_data"]
                )
            else:
                service = BookingService()
                # Ejecutar la reserva en un thread separado
                return await self.loop.run_in_executor(
                    self.executor,
                    service.make_reservation_sync,  # Versión sincrónica del método
                    task["request_data"]
                )
        except Exception as e:
            logging.error(f"Error executing task: {str(e)}")
            raise

    async def add_task(self, request_type: str, request_data: dict) -> str:
        """Agrega una nueva tarea a la cola"""
        task_id = str(uuid.uuid4())
        
        # Crear registro en BD
        db = SessionLocal()
        try:
            db_task = Task(
                task_id=task_id,
                status="PENDING",
                request_type=request_type,
                request_data=request_data
            )
            db.add(db_task)
            db.commit()
        finally:
            db.close()

        # Agregar a la cola
        self.task_queue.put({
            "task_id": task_id,
            "request_type": request_type,
            "request_data": request_data
        })
        
        return task_id

    async def get_task_status(self, task_id: str):
        """Obtiene el estado de una tarea"""
        db = SessionLocal()
        try:
            task = db.query(Task).filter(Task.task_id == task_id).first()
            if not task:
                return None
                
            response = {
                "task_id": task.task_id,
                "status": task.status,
                "created_at": task.created_at.isoformat(),
                "completed_at": task.completed_at.isoformat() if task.completed_at else None
            }
            
            if task.status == "COMPLETED":
                response["result"] = task.result
            elif task.status == "FAILED":
                response["error"] = task.error
                
            return response
        finally:
            db.close()
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from models.schemas import BookingRequest, BookingResponse
from urllib.parse import quote
from datetime import datetime
import logging
import json

class BookingService:
    def __init__(self):
        self.base_url = "https://tecoxp.skedway.com/booking-form.php"
        self.logger = logging.getLogger(__name__)

    async def make_reservation(self, request: BookingRequest) -> BookingResponse:
        """Realiza una reserva basada en los datos proporcionados"""
        driver = None
        try:
            driver = self._setup_driver()
            return await self._perform_booking(driver, request)
        except Exception as e:
            self.logger.error(f"Error en proceso de reserva: {str(e)}")
            raise
        finally:
            if driver:
                driver.quit()

    def _setup_driver(self) -> webdriver.Chrome:
        """Configura y retorna el driver de Chrome"""
        options = webdriver.ChromeOptions()
        #options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        return webdriver.Chrome(options=options)

    async def _perform_booking(self, driver: webdriver.Chrome, request: BookingRequest) -> BookingResponse:
        """Ejecuta el proceso de reserva"""
        try:
            # Construir y cargar URL de reserva
            booking_url = self._build_booking_url(request)
            self.logger.info(f"Intentando reserva con URL: {booking_url}")
            driver.get(booking_url)
            
            # Esperar que cargue el formulario y completar datos
            await self._fill_booking_form(driver, request)
            
            # Realizar la reserva
            return await self._submit_booking(driver, booking_url)
            
        except Exception as e:
            self.logger.error(f"Error en proceso de reserva: {str(e)}")
            raise Exception(f"Error al realizar la reserva: {str(e)}")

    def _build_booking_url(self, request: BookingRequest) -> str:
        """Construye la URL con los parámetros necesarios para la reserva"""
        try:
            start_date = self._format_date_for_url(request.date, request.start_time)
            end_date = self._format_date_for_url(request.date, request.end_time)
            
            params = {
                'baseType': request.base_type,
                'startDate': start_date,
                'endDate': end_date,
                'timezone': 'America/Argentina/Buenos_Aires',
                'from': f'/booking.php?baseType={request.base_type}',
                'action': 'step1',
                'day': quote(request.date),
                'startTime': quote(request.start_time),
                'endTime': quote(request.end_time),
                'companySiteId': request.location_id,
                'buildingId': request.building_id,
                'floorId': request.floor_id,
                'spaceType': '0',
                'order': 'availabilityDesc',
                'page': '1',
                'spaceId[]': request.space_id
            }
            
            url_params = '&'.join([f"{k}={v}" for k, v in params.items()])
            return f"{self.base_url}?{url_params}"
            
        except Exception as e:
            self.logger.error(f"Error construyendo URL: {str(e)}")
            raise

    def _format_date_for_url(self, date_str: str, time_str: str) -> str:
        """Formatea fecha y hora para la URL"""
        try:
            date_obj = datetime.strptime(f"{date_str} {time_str}", "%d/%m/%Y %H:%M")
            return date_obj.strftime("%Y-%m-%d+%H%%3A%M")
        except Exception as e:
            self.logger.error(f"Error formateando fecha: {str(e)}")
            raise

    async def _fill_booking_form(self, driver: webdriver.Chrome, request: BookingRequest):
        """Completa el formulario de reserva"""
        try:
            title_input = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "subject"))
            )
            
            title_input.clear()
            title_input.send_keys(request.title)
            
            await self._verify_form_fields(driver, request)
            
        except TimeoutException:
            raise Exception("Timeout esperando formulario de reserva")
        except Exception as e:
            raise Exception(f"Error completando formulario: {str(e)}")

    async def _verify_form_fields(self, driver: webdriver.Chrome, request: BookingRequest):
        """Verifica que todos los campos del formulario estén correctamente cargados"""
        try:
            date_input = driver.find_element(By.ID, "day")
            if date_input.get_attribute("value") != request.date:
                raise Exception("La fecha no coincide")
            
            start_time = driver.find_element(By.ID, "startTime")
            end_time = driver.find_element(By.ID, "endTime")
            if start_time.get_attribute("value") != request.start_time or \
               end_time.get_attribute("value") != request.end_time:
                raise Exception("Los horarios no coinciden")
            
            space_options = driver.find_elements(By.CSS_SELECTOR, "#space option:checked")
            if not any(opt.get_attribute("value") == request.space_id for opt in space_options):
                raise Exception("El espacio seleccionado no coincide")
                
        except Exception as e:
            self.logger.error(f"Error en verificación de campos: {str(e)}")
            raise

    async def _submit_booking(self, driver: webdriver.Chrome, booking_url: str) -> BookingResponse:
        """Envía el formulario de reserva y verifica la respuesta"""
        try:
            reserve_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button.btn-submit"))
            )
            driver.execute_script("arguments[0].click();", reserve_button)

            success_message = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "[data-notify='message']"))
            )

            if "recibirán pronto un e-mail de confirmación" in success_message.text:
                return BookingResponse(
                    status="success",
                    message="Reserva realizada exitosamente",
                    booking_url=booking_url
                )
            else:
                raise Exception("No se recibió confirmación de la reserva")
                
        except TimeoutException:
            raise Exception("Timeout esperando confirmación de reserva")
        except Exception as e:
            raise Exception(f"Error en proceso de reserva: {str(e)}")

    async def cancel_reservation(self, booking_id: str) -> BookingResponse:
        """[Placeholder] Método para cancelar reservas"""
        raise NotImplementedError("Cancelación de reservas no implementada")
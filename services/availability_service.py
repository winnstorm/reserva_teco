from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, ElementClickInterceptedException
from selenium.webdriver.support.ui import Select
from typing import List, Dict, Optional
from models.schemas import SearchRequest, AvailableSlot
from datetime import datetime
import logging
import time
from dataclasses import dataclass
from typing import List
from urllib.parse import urlparse
import asyncio

@dataclass
class SpaceAvailability:
    space_id: str
    space_name: str
    floor: str
    available_minutes: int
    continuous_slot: bool
    start_time: str
    end_time: str
    page: int
    
    def __lt__(self, other):
        if not isinstance(other, SpaceAvailability):
            return NotImplemented
        return self.available_minutes < other.available_minutes

class AvailabilityService:

    def search_available_slots_sync(self, request_data: dict):
        """Versión sincrónica del método de búsqueda"""
        request = SearchRequest(**request_data)
        
        driver = None
        try:
            driver = self._setup_driver()
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(self._perform_search(driver, request, max_pages=2))
            
            if not result:
                return []

            start_time = datetime.strptime(request.start_time, "%H:%M")
            end_time = datetime.strptime(request.end_time, "%H:%M")
            requested_duration = (end_time - start_time).seconds / 60
            
            scored_spaces = []
            for space in result:
                score = self._calculate_availability_score(space, requested_duration)
                scored_spaces.append((score, space))
            
            scored_spaces.sort(reverse=True, key=lambda x: x[0])
            
            available_spaces = []
            for score, space in scored_spaces[:10]:
                available_slots = [{
                    "start_time": space.start_time,
                    "end_time": space.end_time,
                    "duration": space.available_minutes
                }]
                
                space_info = {
                    "space_id": space.space_id,
                    "space_name": space.space_name,
                    "floor": space.floor,
                    "score": score,
                    "available_slots": available_slots,
                    "availability": {
                        "start_time": space.start_time,
                        "end_time": space.end_time,
                        "continuous_slot": space.continuous_slot,
                        "available_minutes": space.available_minutes
                    }
                }
                available_spaces.append(space_info)
            
            return available_spaces
                
        finally:
            if driver:
                driver.quit()
                
    def __init__(self):
        self.base_url = "https://tecoxp.skedway.com/booking.php"
        self.logger = logging.getLogger(__name__)
        
    def _setup_driver(self) -> webdriver.Chrome:
        """Configura y retorna el driver de Chrome"""
        options = webdriver.ChromeOptions()
        #options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--log-level=3')
        options.add_argument('--silent')
        options.add_experimental_option('excludeSwitches', ['enable-logging'])
        return webdriver.Chrome(options=options)

    def _calculate_availability_score(self, space: SpaceAvailability, request_duration: int) -> float:
        """
        Calcula un score de disponibilidad basado en los criterios solicitados
        """
        score = 0.0
        
        if space.continuous_slot:
            score += 20
            
        if space.available_minutes >= request_duration:
            score += 100
        else:
            score += (space.available_minutes / request_duration) * 40
            
        return score

    async def search_available_slots(self, request: SearchRequest, max_pages: int = 5) -> List[Dict]:
        """
        Busca slots disponibles según los criterios especificados
        
        Args:
            request: Objeto SearchRequest con los criterios de búsqueda
            max_pages: Número máximo de páginas a buscar (default: 2)
        """
        driver = None
        try:
            driver = self._setup_driver()
            all_spaces = await self._perform_search(driver, request, max_pages)
            
            if not all_spaces:
                return []
            
            start_time = datetime.strptime(request.start_time, "%H:%M")
            end_time = datetime.strptime(request.end_time, "%H:%M")
            requested_duration = (end_time - start_time).seconds / 60
            
            # Ordenar espacios por score
            scored_spaces = []
            for space in all_spaces:
                score = self._calculate_availability_score(space, requested_duration)
                scored_spaces.append((score, space))
            
            scored_spaces.sort(reverse=True, key=lambda x: x[0])  # Ordenar por score
            
            
            available_spaces = []
            for score, space in scored_spaces[:10]:  # Top 10 mejores opciones
                available_slots = [{
                    "start_time": space.start_time,
                    "end_time": space.end_time,
                    "duration": space.available_minutes
                }]
                
                space_info = {
                    "space_id": space.space_id, 
                    "space_name": space.space_name,
                    "floor": space.floor,
                    "score": score,
                    "available_slots": available_slots,
                    "availability": {
                        "start_time": space.start_time,
                        "end_time": space.end_time,
                        "continuous_slot": space.continuous_slot,
                        "available_minutes": space.available_minutes
                    }
                }
                available_spaces.append(space_info)
            
            return available_spaces
                
        except Exception as e:
            self.logger.error(f"Error en búsqueda de disponibilidad: {str(e)}")
            raise Exception(f"Error en búsqueda de disponibilidad: {str(e)}")
        finally:
            if driver:
                driver.quit()

    async def _ensure_correct_page(self, driver: webdriver.Chrome, request: SearchRequest):
        """
        Asegura que estamos en la página correcta antes de comenzar la búsqueda
        """
        max_attempts = 3
        base_type = "4" if request.booking_type == "parking" else "1"
        expected_url = f"{self.base_url}?baseType={base_type}"
        
        for attempt in range(max_attempts):
            try:
                current_url = driver.current_url
                parsed_current = urlparse(current_url)
                parsed_expected = urlparse(expected_url)
                
                if "baseType" not in current_url or f"baseType={base_type}" not in current_url:
                    self.logger.info(f"Redirigiendo a la página correcta. Intento {attempt + 1}")
                    driver.get(expected_url)
                    
                    WebDriverWait(driver, 15).until(
                        lambda d: "baseType" in d.current_url and 
                                f"baseType={base_type}" in d.current_url
                    )
                    
                    WebDriverWait(driver, 15).until(
                        EC.presence_of_element_located((By.ID, "day"))
                    )
                    
                    WebDriverWait(driver, 15).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, 'a[data-opt="list"]'))
                    )
                    
                    time.sleep(5)
                    break
                else:
                    self.logger.info("Ya estamos en la página correcta")
                    break
                    
            except TimeoutException:
                if attempt == max_attempts - 1:
                    raise Exception("No se pudo cargar la página correcta después de múltiples intentos")
                time.sleep(5)
                continue

    async def _handle_welcome_popup(self, driver: webdriver.Chrome):
        """
        Maneja el popup de bienvenida si está presente
        """
        try:
            close_button = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.ID, "buttonTourEnd"))
            )
            
            try:
                close_button.click()
                self.logger.info("Popup de bienvenida cerrado exitosamente")
                time.sleep(2)
            except Exception as e:
                self.logger.warning(f"Error al cerrar popup de bienvenida: {str(e)}")
                
        except TimeoutException:
            self.logger.info("No se encontró popup de bienvenida")
            pass

    async def _switch_to_list_view(self, driver: webdriver.Chrome):
        """
        Cambia a vista de lista
        """
        try:
            list_view = WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'a[data-opt="list"]'))
            )
            
            driver.execute_script("arguments[0].scrollIntoView(true);", list_view)
            time.sleep(1)
            
            list_view = WebDriverWait(driver, 15).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, 'a[data-opt="list"]'))
            )
            
            try:
                list_view.click()
            except ElementClickInterceptedException:
                driver.execute_script("arguments[0].click();", list_view)
            
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "scheduler-space"))
            )
            
        except Exception as e:
            self.logger.error(f"Error cambiando a vista de lista: {str(e)}")
            raise Exception(f"Error cambiando a vista de lista: {str(e)}")

    async def _apply_filters(self, driver: webdriver.Chrome, request: SearchRequest):
        """
        Aplica los filtros de búsqueda
        """
        try:
            WebDriverWait(driver, 15).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            
            date_input = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "day"))
            )
            driver.execute_script(f"arguments[0].value = '{request.date}'", date_input)
            
            start_time = driver.find_element(By.ID, "startTime")
            end_time = driver.find_element(By.ID, "endTime")
            driver.execute_script(f"arguments[0].value = '{request.start_time}'", start_time)
            driver.execute_script(f"arguments[0].value = '{request.end_time}'", end_time)
            
            time.sleep(2)
            
            building_select = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "companySiteId"))
            )
            select = Select(building_select)
            for option in select.options:
                if request.building in option.text:
                    select.select_by_value(option.get_attribute("value"))
                    break
            
            time.sleep(3)
            
            filter_button = driver.find_element(By.ID, "buttonFilter")
            driver.execute_script("arguments[0].click();", filter_button)
            
            time.sleep(7)
            
            try:
                WebDriverWait(driver, 10).until_not(
                    EC.presence_of_element_located((By.CLASS_NAME, "loading-indicator"))
                )
            except TimeoutException:
                pass
                
            await self._wait_for_spaces_update(driver)
            
        except Exception as e:
            self.logger.error(f"Error al aplicar filtros: {str(e)}")
            raise Exception(f"Error al aplicar filtros: {str(e)}")

    async def _wait_for_spaces_update(self, driver: webdriver.Chrome):
        """
        Espera a que se actualice la lista de espacios
        """
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "scheduler-space"))
            )
        except TimeoutException:
            raise Exception("Timeout esperando actualización de espacios")

    async def _perform_search(self, driver: webdriver.Chrome, request: SearchRequest, max_pages: int) -> List[SpaceAvailability]:
        """
        Realiza la búsqueda completa en todos los pisos y páginas
        """
        await self._ensure_correct_page(driver, request)
        await self._handle_welcome_popup(driver)
        
        all_spaces = []
        
        floor_select = Select(driver.find_element(By.ID, "floorId"))
        floors = [option.text for option in floor_select.options]
        
        for floor in floors:
            self.logger.info(f"Buscando en piso: {floor}")
            floor_select = Select(driver.find_element(By.ID, "floorId"))
            floor_select.select_by_visible_text(floor)
            time.sleep(2)
            
            await self._switch_to_list_view(driver)
            await self._apply_filters(driver, request)
            
            page = 1
            while page <= max_pages:
                spaces = await self._analyze_page_spaces(driver, floor, page)
                if not spaces:
                    break
                    
                all_spaces.extend(spaces)
                
                if page >= max_pages:
                    break
                
                try:
                    pagination = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.CLASS_NAME, "pagination"))
                    )
                    
                    next_page_buttons = driver.find_elements(By.CSS_SELECTOR, f"a.page-link[data-page='{page + 1}']")
                    
                    if not next_page_buttons:
                        break
                    
                    next_page = next_page_buttons[0]
                    
                    driver.execute_script(
                        "arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'});", 
                        next_page
                    )
                    time.sleep(1)
                    
                    next_page = WebDriverWait(driver, 10).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, f"a.page-link[data-page='{page + 1}']"))
                    )
                    
                    try:
                        next_page.click()
                    except Exception:
                        try:
                            driver.execute_script("arguments[0].click();", next_page)
                        except Exception:
                            actions = webdriver.ActionChains(driver)
                            actions.move_to_element(next_page).click().perform()
                    
                    time.sleep(2)
                    
                    WebDriverWait(driver, 10).until(
                        lambda d: d.find_element(By.CSS_SELECTOR, "li.page-item.active a").get_attribute("data-page") == str(page + 1)
                    )
                    
                    page += 1
                    
                except TimeoutException:
                    self.logger.warning(f"Timeout esperando paginación en página {page}")
                    break
                except Exception as e:
                    self.logger.error(f"Error en paginación: {str(e)}")
                    break
                    
        return all_spaces

    async def _analyze_page_spaces(self, driver: webdriver.Chrome, floor: str, page: int) -> List[SpaceAvailability]:
        """
        Analiza los espacios disponibles en la página actual
        """
        spaces = []
        space_elements = driver.find_elements(By.CLASS_NAME, "scheduler-space")
        
        for space_elem in space_elements:
            try:
                h5_element = space_elem.find_element(By.TAG_NAME, "h5")
                full_text = h5_element.text
                space_name = full_text.split('|')[0].replace('favorite_border', '').strip()
                
                # Ignorar espacios para motos
                if "EHOBA-MOTO" in space_name:
                    continue
                    
                space_id = space_elem.get_attribute("data-space-id")
                
                time_blocks = space_elem.find_elements(By.CLASS_NAME, "block-free")
                if not time_blocks:
                    continue
                    
                current_block = {"start": None, "end": None, "minutes": 0}
                longest_block = {"start": None, "end": None, "minutes": 0}
                
                for block in time_blocks:
                    start_time = block.get_attribute("data-time-start")
                    end_time = block.get_attribute("data-time-end")
                    
                    if current_block["start"] is None:
                        current_block = {"start": start_time, "end": end_time, "minutes": 30}
                    elif self._times_are_consecutive(current_block["end"], start_time):
                        current_block["end"] = end_time
                        current_block["minutes"] += 30
                    else:
                        if current_block["minutes"] > longest_block["minutes"]:
                            longest_block = current_block.copy()
                        current_block = {"start": start_time, "end": end_time, "minutes": 30}
                
                if current_block["minutes"] > longest_block["minutes"]:
                    longest_block = current_block
                    
                if longest_block["minutes"] >= 30:
                    spaces.append(SpaceAvailability(
                        space_id=space_id,
                        space_name=space_name, 
                        floor=floor,
                        available_minutes=longest_block["minutes"],
                        continuous_slot=longest_block["minutes"] >= 60,
                        start_time=longest_block["start"],
                        end_time=longest_block["end"],
                        page=page
                    ))
                    
            except Exception as e:
                self.logger.warning(f"Error analizando espacio: {str(e)}")
                continue
                
        return spaces

    def _times_are_consecutive(self, time1: str, time2: str) -> bool:
        """
        Verifica si dos horarios son consecutivos
        """
        try:
            hours1, minutes1 = map(int, time1.split(':'))
            hours2, minutes2 = map(int, time2.split(':'))
            
            total_minutes1 = hours1 * 60 + minutes1
            total_minutes2 = hours2 * 60 + minutes2
            
            return total_minutes2 - total_minutes1 <= 30
        except:
            return False

    def _is_valid_range(self, time_range: Dict[str, str]) -> bool:
        """
        Verifica si un rango de tiempo es válido (al menos 30 minutos)
        """
        try:
            start_hours, start_minutes = map(int, time_range["start"].split(':'))
            end_hours, end_minutes = map(int, time_range["end"].split(':'))
            
            total_start = start_hours * 60 + start_minutes
            total_end = end_hours * 60 + end_minutes
            
            return total_end - total_start >= 30
        except:
            return False
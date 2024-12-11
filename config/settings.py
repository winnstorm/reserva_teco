from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    app_name: str = "Parking Automation System"
    debug: bool = True
    base_url: str = "https://tecoxp.skedway.com"
    database_url: str = "sqlite:///./parking_system.db"
    max_workers: int = 1  # Número máximo de trabajadores concurrentes
    
    # Configuración de Chrome
    chrome_options: list = [
        #"--headless",
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu",
        "--log-level=3",  # Silencia los logs de Chrome
        "--disable-logging",
        "--silent"
    ]
    
    class Config:
        env_file = ".env"
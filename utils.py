import random
import asyncio
import logging
from datetime import datetime
from pathlib import Path

def setup_logging(log_dir="logs"):
    """Настройка логирования с использованием заданной директории"""
    log_path = Path(log_dir)
    log_path.mkdir(exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_path / f"scraper_{datetime.now().strftime('%Y%m%d')}.log"),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

async def random_delay(min_sec, max_sec, async_mode=True):
    """Случайная задержка (асинхронная или синхронная)"""
    delay = random.uniform(min_sec, max_sec)
    if async_mode:
        await asyncio.sleep(delay)
    else:
        import time
        time.sleep(delay)
    return delay

async def human_like_mouse_movement(page, element=None):
    """Имитация движения мыши (асинхронная)"""
    viewport = page.viewport_size
    if not viewport:
        return
    
    # Случайные движения по экрану
    for _ in range(random.randint(2, 5)):
        x = random.randint(0, viewport['width'])
        y = random.randint(0, viewport['height'])
        await page.mouse.move(x, y, steps=random.randint(5, 10))
        await asyncio.sleep(random.uniform(0.1, 0.3))
    
    if element:
        box = await element.bounding_box()
        if box:
            target_x = box['x'] + box['width'] / 2
            target_y = box['y'] + box['height'] / 2
            # Плавное движение к элементу
            await page.mouse.move(target_x, target_y, steps=random.randint(10, 20))
            await asyncio.sleep(random.uniform(0.1, 0.3))

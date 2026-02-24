import threading
import time
from typing import Optional

from ..logging_config import get_logger
from .config import ParserConfig
from .updater import RatesUpdater


class Scheduler:
    """
    Планировщик периодического обновления курсов.
    Запускается в отдельном потоке.
    """

    def __init__(self, config: Optional[ParserConfig] = None):
        self.config = config or ParserConfig.from_env()
        self.updater = RatesUpdater(self.config)
        self.logger = get_logger("scheduler")
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._is_running = False

    @property
    def is_running(self) -> bool:
        """Возвращает True, если поток планировщика активен."""
        return self._is_running and self._thread is not None and self._thread.is_alive()

    def start(self):
        """Запуск планировщика в отдельном потоке."""
        if self.is_running:
            self.logger.warning("Планировщик уже запущен")
            return

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        self._is_running = True
        self.logger.info("Планировщик запущен")

    def stop(self):
        """Остановка планировщика."""
        if not self.is_running:
            return

        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=3)
        self._is_running = False
        self.logger.info("Планировщик остановлен")

    def _run_loop(self):
        """Основной цикл планировщика."""
        interval = self.config.UPDATE_INTERVAL_MINUTES * 60  # в секундах
        while not self._stop_event.is_set():
            try:
                self.logger.debug("Запуск планового обновления...")
                self.updater.run_update()
                # Ждём interval, но с проверкой stop_event каждые 0.5 сек
                for _ in range(interval * 2):
                    if self._stop_event.is_set():
                        break
                    time.sleep(0.5)
            except Exception as e:
                self.logger.error(f"Ошибка в цикле планировщика: {e}")
                # Пауза перед повторной попыткой
                time.sleep(5)

    def run_once(self):
        """Однократное обновление (синхронно)."""
        return self.updater.run_update()

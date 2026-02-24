from datetime import datetime
from typing import Dict, Optional

from ..core.exceptions import ApiRequestError
from ..logging_config import setup_logging
from .api_clients import CoinGeckoClient, ExchangeRateApiClient
from .config import ParserConfig
from .storage import ParserStorage

logger = setup_logging()  # получим логгер


class RatesUpdater:
    """Обновляет курсы валют из внешних источников."""

    def __init__(self, config: Optional[ParserConfig] = None):
        self.config = config or ParserConfig()
        self.config.validate()
        self.storage = ParserStorage()

        self.clients = {
            "coingecko": CoinGeckoClient(self.config),
            "exchangerate": ExchangeRateApiClient(self.config),
        }

    def run_update(self, source: Optional[str] = None) -> Dict[str, float]:
        """
        Запускает обновление курсов.
        source: если указан, обновляет один источник coingecko/exchangerate
        Возвращает словарь всех полученных курсов.
        """
        logger.info("Запуск обновления курсов...")
        all_rates = {}
        successful_sources = []

        sources_to_update = [source] if source else list(self.clients.keys())

        for source_name in sources_to_update:
            if source_name not in self.clients:
                logger.warning(f"Неизвестный источник: {source_name}")
                continue

            client = self.clients[source_name]
            try:
                logger.info(f"Запрос к {source_name}...")
                rates = client.fetch_rates()
                if not rates:
                    logger.warning(f"Нет данных от {source_name}")
                    continue

                logger.info(f"Получено {len(rates)} курсов от {source_name}")

                # Сохраняем каждую пару в историю
                for pair_key, rate in rates.items():
                    try:
                        from_cur, to_cur = pair_key.split("_")
                        rate_record = {
                            "from_currency": from_cur,
                            "to_currency": to_cur,
                            "rate": rate,
                            "source": source_name,
                            "meta": {"request_timestamp": datetime.now().isoformat()},
                        }
                        self.storage.save_exchange_rate(rate_record)
                    except Exception as e:
                        logger.error(f"Ошибка сохранения пары {pair_key}: {e}")

                all_rates.update(rates)
                successful_sources.append(source_name)

            except ApiRequestError as e:
                logger.error(f"Ошибка API {source_name}: {e}")
            except Exception as e:
                logger.error(
                    f"Непредвиденная ошибка при обращении к {source_name}: {e}"
                )

        if all_rates:
            source_str = ",".join(successful_sources)
            self.storage.save_current_rates(all_rates, source_str)
            logger.info(
                f"Обновление завершено. Всего пар: {len(all_rates)}."
                f"Источники: {source_str}"
            )
        else:
            logger.warning("Не удалось получить ни одного курса.")
        
        return all_rates
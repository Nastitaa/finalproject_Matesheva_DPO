#!/usr/bin/env python3
"""Интерфейс командной строки."""

import functools
import shlex
import sys
from typing import List, Optional

from prettytable import PrettyTable

from ..core import usecases
from ..core.exceptions import (
    ApiRequestError,
    CurrencyNotFoundError,
    InsufficientFundsError,
)
from ..infra.database import DatabaseManager
from ..parser_service.scheduler import Scheduler

db = DatabaseManager()


def catch_domain_errors(func):
    """Декоратор для обработки доменных исключений в методах команд."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except CurrencyNotFoundError as e:
            print(
                f"Ошибка: {e}. Поддерживаемые валюты: "
                "USD, EUR, RUB, GBP, JPY, CNY, BTC, ETH, SOL, ADA, DOT."
            )
        except InsufficientFundsError as e:
            print(f"Ошибка: {e}")
        except ApiRequestError as e:
            print(f"Ошибка получения курса: {e}. Попробуйте позже.")
        except ValueError as e:
            print(f"Ошибка ввода: {e}")
        except Exception as e:
            print(f"Непредвиденная ошибка: {e}")

    return wrapper


class CLI:
    """Главный класс интерфейса командной строки."""

    def __init__(self):
        self.current_user = None
        self.scheduler = None
        self.commands = {
            "register": self.cmd_register,
            "login": self.cmd_login,
            "show-portfolio": self.cmd_show_portfolio,
            "buy": self.cmd_buy,
            "sell": self.cmd_sell,
            "get-rate": self.cmd_get_rate,
            "update-rates": self.cmd_update_rates,
            "show-rates": self.cmd_show_rates,
            "scheduler-start": self.cmd_scheduler_start,
            "scheduler-stop": self.cmd_scheduler_stop,
            "scheduler-status": self.cmd_scheduler_status,
            "exit": self.cmd_exit,
            "help": self.cmd_help,
        }

    def run(self):
        """Запуск основного цикла."""
        print("Добро пожаловать в Валютный кошелёк! Введите 'help' для списка команд.")
        while True:
            try:
                line = input("> ").strip()
                if not line:
                    continue
                parts = shlex.split(line)
                cmd = parts[0].lower()
                args = parts[1:]

                if cmd in self.commands:
                    self.commands[cmd](args)
                else:
                    print(f"Неизвестная команда: {cmd}. Введите 'help'.")
            except EOFError:
                print("\nВыход.")
                break
            except KeyboardInterrupt:
                print("\nВыход.")
                break

    # ---------- Команды пользователей ----------
    @catch_domain_errors
    def cmd_register(self, args: List[str]):
        """Регистрация нового пользователя."""
        parser = self._parse_args(args, expected=("--username", "--password"))
        if not parser:
            return
        username = parser.get("--username")
        password = parser.get("--password")
        user = usecases.UserService.register(username, password)
        print(
            f"Пользователь '{user.username}' зарегистрирован (id={user.user_id}). "
            f"Войдите: login --username {user.username} --password ****"
        )

    @catch_domain_errors
    def cmd_login(self, args: List[str]):
        """Вход в систему."""
        parser = self._parse_args(args, expected=("--username", "--password"))
        if not parser:
            return
        username = parser.get("--username")
        password = parser.get("--password")
        user = usecases.UserService.login(username, password)
        self.current_user = user
        print(f"Вы вошли как '{user.username}'")

    # ---------- Команды портфеля ----------
    @catch_domain_errors
    def cmd_show_portfolio(self, args: List[str]):
        """Показать портфель пользователя."""
        if not self._require_login():
            return
        parser = self._parse_args(args, optional=("--base",))
        base = parser.get("--base", "USD").upper()

        service = usecases.PortfolioService(self.current_user)
        portfolio = service.get_portfolio()

        if not portfolio.wallets:
            print("Ваш портфель пуст.")
            return

        table = PrettyTable()
        table.field_names = ["Валюта", "Баланс", f"Стоимость в {base} (курс)"]

        total = 0.0
        stale_currencies = []

        for code, wallet in portfolio.wallets.items():
            if code == base:
                value = wallet.balance
                rate_display = "1.0"
            else:
                rate, updated_at, is_fresh = usecases._get_cached_rate(code, base)
                if rate is None:
                    value = None
                    rate_display = "N/A"
                else:
                    value = wallet.balance * rate
                    rate_display = f"{rate:.6f}"
                    if not is_fresh:
                        stale_currencies.append(code)

            if value is None:
                table.add_row([code, f"{wallet.balance:.4f}", "— (нет курса)"])
            else:
                table.add_row(
                    [code, f"{wallet.balance:.4f}", f"{value:.2f} ({rate_display})"]
                )
                total += value

        print(table)
        print(f"ИТОГО: {total:.2f} {base}")
        if stale_currencies:
            print(
                f"Примечание: курсы для {', '.join(stale_currencies)} устарели."
                " Выполните update-rates для обновления."
            )

    @catch_domain_errors
    def cmd_buy(self, args: List[str]):
        """Купить валюту."""
        if not self._require_login():
            return
        parser = self._parse_args(
            args, expected=("--currency", "--amount"), optional=("--base",)
        )
        if not parser:
            return
        currency = parser.get("--currency").upper()
        amount_str = parser.get("--amount")
        base = parser.get("--base", "USD").upper()

        service = usecases.PortfolioService(self.current_user)
        result = service.buy_currency(currency, amount_str, base)
        print(
            f"Покупка выполнена: {result['amount']:.4f} "
            f"{result['currency']} по курсу {result['rate']:.6f} "
            f"{result['base_currency']}/{result['currency']}"
        )
        print(
            f"Списано {result['cost']:.2f} "
            f"{result['base_currency']}. Новый баланс"
            f"{result['base_currency']}: {result['base_balance']:.2f}"
        )
        print(f"Баланс {result['currency']}: {result['new_balance']:.4f}")

    @catch_domain_errors
    def cmd_sell(self, args: List[str]):
        """Продать валюту."""
        if not self._require_login():
            return
        parser = self._parse_args(
            args, expected=("--currency", "--amount"), optional=("--base",)
        )
        if not parser:
            return
        currency = parser.get("--currency").upper()
        amount_str = parser.get("--amount")
        base = parser.get("--base", "USD").upper()

        service = usecases.PortfolioService(self.current_user)
        result = service.sell_currency(currency, amount_str, base)
        print(
            f"Продажа выполнена: {result['amount']:.4f}"
            f" {result['currency']} по курсу {result['rate']:.6f} "
            f"{result['base_currency']}/{result['currency']}"
        )
        print(
            f"Зачислено {result['proceeds']:.2f} "
            f"{result['base_currency']}. Новый баланс "
            f"{result['base_currency']}: {result['base_balance']:.2f}"
        )
        print(f"Баланс {result['currency']}: {result['new_balance']:.4f}")

    # ---------- Команды курсов ----------
    @catch_domain_errors
    def cmd_get_rate(self, args: List[str]):
        """Получить текущий курс (только свежие данные)."""
        parser = self._parse_args(args, expected=("--from", "--to"))
        if not parser:
            return
        from_cur = parser.get("--from").upper()
        to_cur = parser.get("--to").upper()

        rate, updated_at = usecases.RateService.get_rate(from_cur, to_cur)
        ts_str = updated_at.strftime("%Y-%m-%d %H:%M:%S")
        print(f"Курс {from_cur}→{to_cur}: {rate:.6f} (обновлено: {ts_str})")
        inv_rate, inv_updated, _ = usecases._get_cached_rate(to_cur, from_cur)
        if inv_rate:
            print(f"Обратный курс {to_cur}→{from_cur}: {inv_rate:.6f}")

    @catch_domain_errors
    def cmd_update_rates(self, args: List[str]):
        """Однократное обновление курсов из внешних источников."""
        parser = self._parse_args(args, optional=("--source",))
        source = parser.get("--source")

        from ..parser_service.updater import RatesUpdater

        updater = RatesUpdater()
        rates = updater.run_update(source)
        if rates:
            print(f"Обновление выполнено. Получено {len(rates)} курсов.")
        else:
            print("Не удалось обновить курсы. Проверьте логи.")

    @catch_domain_errors
    def cmd_show_rates(self, args: List[str]):
        """Показать курсы из кэша (с фильтрацией)."""
        parser = self._parse_args(args, optional=("--currency", "--top", "--base"))
        currency_filter = parser.get("--currency")
        top = parser.get("--top")
        base = parser.get("--base", "USD").upper()

        rates_data = db.load_rates_cache()
        pairs = rates_data.get("pairs", {})
        last_refresh = rates_data.get("last_refresh", "никогда")

        if not pairs:
            print("Кэш курсов пуст. Выполните 'update-rates' для загрузки.")
            return

        filtered = []
        for pair_key, info in pairs.items():
            if "_" not in pair_key:
                continue
            from_cur, to_cur = pair_key.split("_", 1)
            if to_cur != base:
                continue
            if currency_filter and from_cur != currency_filter.upper():
                continue
            filtered.append((from_cur, info["rate"], info["updated_at"]))

        if not filtered:
            print("Нет данных для указанных фильтров.")
            return

        if top:
            try:
                top_n = int(top)
                filtered.sort(key=lambda x: x[1], reverse=True)
                filtered = filtered[:top_n]
            except ValueError:
                print("--top должен быть числом")
                return

        table = PrettyTable()
        table.field_names = ["Валюта", f"Курс к {base}", "Обновлено"]
        for cur, rate, ts in filtered:
            table.add_row([cur, f"{rate:.6f}", ts])

        print(f"Курсы из кэша (обновлено: {last_refresh}):")
        print(table)

    # ---------- Команды планировщика ----------
    @catch_domain_errors
    def cmd_scheduler_start(self, args: List[str]):
        """Запустить автоматическое обновление курсов."""
        if self.scheduler is None:
            self.scheduler = Scheduler()
        if self.scheduler.is_running:
            print("Планировщик уже запущен.")
        else:
            self.scheduler.start()
            print(
                "Планировщик запущен. Курсы будут обновляться каждые {} минут.".format(
                    self.scheduler.config.UPDATE_INTERVAL_MINUTES
                )
            )

    @catch_domain_errors
    def cmd_scheduler_stop(self, args: List[str]):
        """Остановить автоматическое обновление."""
        if self.scheduler and self.scheduler.is_running:
            self.scheduler.stop()
            print("Планировщик остановлен.")
        else:
            print("Планировщик не запущен.")

    @catch_domain_errors
    def cmd_scheduler_status(self, args: List[str]):
        """Показать статус планировщика."""
        if self.scheduler and self.scheduler.is_running:
            print(
                "Планировщик работает (интервал обновления: {} мин).".format(
                    self.scheduler.config.UPDATE_INTERVAL_MINUTES
                )
            )
        else:
            print("Планировщик не активен.")

    # ---------- Выход и справка ----------
    @catch_domain_errors
    def cmd_exit(self, args):
        """Выход из программы."""
        if self.scheduler and self.scheduler.is_running:
            self.scheduler.stop()
        print("До свидания!")
        sys.exit(0)

    def cmd_help(self, args):
        """Показать справку."""
        table = PrettyTable()
        table.field_names = ["Команда", "Описание"]
        table.align["Команда"] = "l"
        table.align["Описание"] = "l"
        table.max_width["Описание"] = 60

        table.add_row(
            [
                "register --username USERNAME --password PASSWORD",
                "Зарегистрировать пользователя. Пароль > 4 символов.",
            ]
        )
        table.add_row(
            ["login --username USERNAME --password PASSWORD", "Войти в систему."]
        )
        table.add_row(
            ["show-portfolio [--base BASE]", "Показать все кошельки в базовой валюте."]
        )
        table.add_row(
            ["buy --currency CUR --amount AMOUNT [--base BASE]", "Купить валюту."]
        )
        table.add_row(
            ["sell --currency CUR --amount AMOUNT [--base BASE]", "Продать валюту."]
        )
        table.add_row(["get-rate --from FROM --to TO", "Получить текущий курс."])
        table.add_row(
            [
                "show-rates [--currency CUR] [--top N] [--base BASE]",
                "Показать курсы. Фильтр по валюте, топ N самых дорогих, смена базовой валюты.",
            ]
        )
        table.add_row(
            [
                "update-rates [--source coingecko|exchangerate]",
                "Однократно обновить курсы валют.",
            ]
        )
        table.add_row(["scheduler-start", "Запустить фоновое обновление курсов."])
        table.add_row(["scheduler-stop", "Остановить фоновое обновление."])
        table.add_row(["scheduler-status", "Показать, запущен ли планировщик."])
        table.add_row(["exit", "Выйти из программы."])
        table.add_row(["help", "Показать эту справку."])

        print("Доступные команды:")
        print(table)

    # ---------- Вспомогательные методы ----------
    def _require_login(self) -> bool:
        if self.current_user is None:
            print("Необходимо войти в систему. Используйте 'login'.")
            return False
        return True

    def _parse_args(
        self, args: List[str], expected: tuple = (), optional: tuple = ()
    ) -> Optional[dict]:
        """
        Простой парсер аргументов вида --key value.
        Возвращает словарь {key: value} или None при ошибке.
        """
        result = {}
        i = 0
        while i < len(args):
            if args[i].startswith("--"):
                key = args[i]
                if i + 1 < len(args) and not args[i + 1].startswith("--"):
                    result[key] = args[i + 1]
                    i += 2
                else:
                    print(f"Ошибка: аргумент {key} должен иметь значение")
                    return None
            else:
                print(f"Неизвестный аргумент: {args[i]}")
                return None

        for req in expected:
            if req not in result:
                print(f"Ошибка: обязательный аргумент {req} отсутствует")
                return None
        return result

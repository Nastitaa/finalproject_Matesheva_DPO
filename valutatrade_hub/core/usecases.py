from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple

from ..decorators import log_action
from ..infra.database import DatabaseManager
from ..infra.settings import SettingsLoader
from ..logging_config import get_logger
from . import utils  # для validate_amount
from .currencies import get_currency
from .exceptions import ApiRequestError, InsufficientFundsError
from .models import Portfolio, User

db = DatabaseManager()
settings = SettingsLoader()
RATES_TTL = settings.get("rates_ttl_seconds", 300)


def _get_cached_rate(
    from_cur: str, to_cur: str
) -> Tuple[Optional[float], Optional[datetime], bool]:
    """
    Возвращает курс из кэша (rates.json), время обновления и флаг свежести.
    Если пара отсутствует, возвращает (None, None, False).
    """
    rates_data = db.load_rates_cache()
    pair_key = f"{from_cur.upper()}_{to_cur.upper()}"
    pair_info = rates_data.get("pairs", {}).get(pair_key)

    if not pair_info:
        return None, None, False

    rate = pair_info.get("rate")
    updated_at_str = pair_info.get("updated_at")
    if not rate or not updated_at_str:
        return None, None, False

    try:
        updated_at = datetime.fromisoformat(updated_at_str.replace("Z", "+00:00"))
    except ValueError:
        return None, None, False

    now = datetime.now(updated_at.tzinfo) if updated_at.tzinfo else datetime.now()
    is_fresh = (now - updated_at) < timedelta(seconds=RATES_TTL)
    return rate, updated_at, is_fresh


class UserService:
    """Сервис для работы с пользователями."""

    @staticmethod
    @log_action("REGISTER")
    def register(username: str, password: str) -> User:
        """Регистрация нового пользователя."""
        if not username or not username.strip():
            raise ValueError("Имя пользователя не может быть пустым")
        if len(password) < 4:
            raise ValueError("Пароль должен быть не короче 4 символов")

        users_data = db.load_users()
        # Проверка уникальности
        for u in users_data:
            if u["username"] == username:
                raise ValueError(f"Имя пользователя '{username}' уже занято")

        # Генерация ID
        new_id = max([u["user_id"] for u in users_data], default=0) + 1

        # Создание пользователя
        user = User(new_id, username, password)

        # Сохранение
        users_data.append(user.to_dict())
        db.save_users(users_data)

        # Создание пустого портфеля
        portfolio = Portfolio(user.user_id)
        portfolios_data = db.load_portfolios()
        portfolios_data.append(portfolio.to_dict())
        db.save_portfolios(portfolios_data)

        return user

    @staticmethod
    @log_action("LOGIN")
    def login(username: str, password: str) -> User:
        """Аутентификация пользователя."""
        users_data = db.load_users()
        for u_data in users_data:
            if u_data["username"] == username:
                user = User.from_dict(u_data)
                if user.verify_password(password):
                    return user
                else:
                    raise ValueError("Неверный пароль")
        raise ValueError(f"Пользователь '{username}' не найден")


class PortfolioService:
    """Сервис для управления портфелем."""

    def __init__(self, user: User):
        self.user = user
        self._portfolio = self._load_portfolio()

    def _load_portfolio(self) -> Portfolio:
        portfolios_data = db.load_portfolios()
        for p in portfolios_data:
            if p["user_id"] == self.user.user_id:
                return Portfolio.from_dict(p)
        # Если портфеля нет, создаём новый
        new_portfolio = Portfolio(self.user.user_id)
        portfolios_data.append(new_portfolio.to_dict())
        db.save_portfolios(portfolios_data)
        return new_portfolio

    def _save_portfolio(self):
        portfolios_data = db.load_portfolios()
        for i, p in enumerate(portfolios_data):
            if p["user_id"] == self.user.user_id:
                portfolios_data[i] = self._portfolio.to_dict()
                break
        else:
            portfolios_data.append(self._portfolio.to_dict())
        db.save_portfolios(portfolios_data)

    def get_portfolio(self) -> Portfolio:
        return self._portfolio

    def _get_or_create_wallet(self, currency_code):
        wallet = self._portfolio.get_wallet(currency_code)
        if wallet is None:
            self._portfolio.add_currency(currency_code)
            wallet = self._portfolio.get_wallet(currency_code)
        return wallet

    def _prepare_transaction(
        self, currency_code: str, amount: str, base_currency: str, transaction_type: str
    ):
        """
        Подготавливает данные для транзакции покупки/продажи.
        Возвращает (amount_float, rate, wallet_from, wallet_to, is_fresh)
        """
        amount_float = utils.validate_amount(amount)
        currency = get_currency(currency_code)

        rate, updated_at, is_fresh = _get_cached_rate(currency.code, base_currency)
        if rate is None:
            raise ApiRequestError(
                f"Курс {currency.code}→{base_currency} "
                "недоступен. Выполните update-rates."
            )
        if not is_fresh:
            raise ApiRequestError(
                f"Курс {currency.code}→{base_currency} "
                "устарел. Выполните update-rates."
            )

        # Кошелёк для валюты, которая будет списываться (зависит от типа)
        if transaction_type == "buy":
            wallet_from = self._get_or_create_wallet(base_currency)
            wallet_to = self._get_or_create_wallet(currency.code)
            required = amount_float * rate
            if wallet_from.balance < required:
                raise InsufficientFundsError(
                    wallet_from.balance, required, base_currency
                )
        elif transaction_type == "sell":
            wallet_from = self._get_or_create_wallet(currency.code)
            wallet_to = self._get_or_create_wallet(base_currency)
            required = amount_float
            if wallet_from.balance < required:
                raise InsufficientFundsError(
                    wallet_from.balance, required, currency.code
                )
        else:
            raise ValueError(f"Неизвестный тип транзакции: {transaction_type}")

        return amount_float, rate, wallet_from, wallet_to, is_fresh

    @log_action("BUY")
    def buy_currency(
        self, currency_code: str, amount: str, base_currency: str = "USD"
    ) -> Dict[str, Any]:
        """
        Покупка валюты.
        Возвращает словарь с информацией о транзакции.
        """
        amount_float, rate, base_wallet, target_wallet, is_fresh = (
            self._prepare_transaction(currency_code, amount, base_currency, "buy")
        )
        cost = amount_float * rate
        base_wallet.withdraw(cost)
        target_wallet.deposit(amount_float)
        self._save_portfolio()
        return {
            "currency": currency_code.code,
            "amount": amount_float,
            "rate": rate,
            "cost": cost,
            "base_currency": base_currency,
            "new_balance": target_wallet.balance,
            "base_balance": base_wallet.balance,
            "rate_fresh": is_fresh,
        }

    @log_action("SELL")
    def sell_currency(
        self, currency_code: str, amount: str, base_currency: str = "USD"
    ) -> Dict[str, Any]:
        """Продажа указанного количества валюты."""
        amount_float, rate, wallet_from, wallet_to, is_fresh = (
            self._prepare_transaction(currency_code, amount, base_currency, "sell")
        )
        proceeds = amount_float * rate

        wallet_from.withdraw(amount_float)
        wallet_to.deposit(proceeds)

        if not is_fresh:
            logger = get_logger("usecases")
            logger.warning(
                f"Курс {currency_code}→{base_currency} устарел."
                " Операция выполнена по устаревшему курсу."
            )

        self._save_portfolio()

        return {
            "currency": currency_code.upper(),
            "amount": amount_float,
            "rate": rate,
            "proceeds": proceeds,
            "base_currency": base_currency,
            "new_balance": wallet_from.balance,
            "base_balance": wallet_to.balance,
            "rate_fresh": is_fresh,
        }


class RateService:
    """Сервис для получения курсов."""

    @staticmethod
    @log_action("GET_RATE")
    def get_rate(from_code: str, to_code: str) -> Tuple[float, datetime]:
        """Возвращает курс и время последнего обновления (только свежие данные)."""
        from_cur = get_currency(from_code)
        to_cur = get_currency(to_code)

        rate, updated_at, is_fresh = _get_cached_rate(from_cur.code, to_cur.code)
        if rate is None:
            raise ApiRequestError(f"Курс {from_code}→{to_code} отсутствует в кэше.")
        if not is_fresh:
            raise ApiRequestError(
                f"Курс {from_code}→{to_code} устарел. Выполните update-rates."
            )
        return rate, updated_at

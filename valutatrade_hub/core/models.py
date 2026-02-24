import os
from datetime import datetime
from typing import Dict, Optional

from .utils import hash_password


class User:
    """Класс пользователя."""

    def __init__(
        self,
        user_id: int,
        username: str,
        password: str,
        registration_date: Optional[str] = None,
    ):
        if not username:
            raise ValueError("Username cannot be empty")
        if len(password) < 4:
            raise ValueError("Password must be at least 4 characters")

        self._user_id = user_id
        self._username = username
        self._salt = os.urandom(16).hex()
        self._hashed_password = hash_password(password, self._salt)
        if registration_date is None:
            registration_date = datetime.now().isoformat()
        self._registration_date = registration_date

    @property
    def user_id(self) -> int:
        return self._user_id

    @property
    def username(self) -> str:
        return self._username

    @property
    def registration_date(self) -> str:
        return self._registration_date

    def get_user_info(self) -> dict:
        return {
            "user_id": self._user_id,
            "username": self._username,
            "registration_date": self._registration_date,
        }

    def change_password(self, new_password: str) -> None:
        if len(new_password) < 4:
            raise ValueError("Password must be at least 4 characters")
        self._hashed_password = hash_password(new_password, self._salt)

    def verify_password(self, password: str) -> bool:
        return self._hashed_password == hash_password(password, self._salt)

    def to_dict(self) -> dict:
        return {
            "user_id": self._user_id,
            "username": self._username,
            "hashed_password": self._hashed_password,
            "salt": self._salt,
            "registration_date": self._registration_date,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "User":
        user = cls.__new__(cls)
        user._user_id = data["user_id"]
        user._username = data["username"]
        user._hashed_password = data["hashed_password"]
        user._salt = data["salt"]
        user._registration_date = data["registration_date"]
        return user


class Wallet:
    """Кошелёк для одной валюты."""

    def __init__(self, currency_code: str, balance: float = 0.0):
        self.currency_code = currency_code.upper()
        # Валидация баланса через validate_amount (принимает float, но для единообразия)
        # В конструкторе balance может быть 0, поэтому пропускаем через проверку.
        if balance < 0:
            raise ValueError("Initial balance cannot be negative")
        self._balance = balance

    @property
    def balance(self) -> float:
        return self._balance

    @balance.setter
    def balance(self, value: float):
        if value < 0:
            raise ValueError("Balance cannot be negative")
        self._balance = value

    def deposit(self, amount: float) -> None:
        """Пополнение кошелька."""
        if amount <= 0:
            raise ValueError("Deposit amount must be positive")
        self._balance += amount

    def withdraw(self, amount: float) -> None:
        """Снятие средств. При нехватке средств выбрасывает InsufficientFundsError."""
        if amount <= 0:
            raise ValueError("Withdrawal amount must be positive")
        if self._balance < amount:
            from .exceptions import InsufficientFundsError

            raise InsufficientFundsError(self._balance, amount, self.currency_code)
        self._balance -= amount

    def get_balance_info(self) -> str:
        return f"{self.balance:.2f} {self.currency_code}"

    def to_dict(self) -> dict:
        return {"balance": self._balance}

    @classmethod
    def from_dict(cls, currency_code: str, data: dict) -> "Wallet":
        return cls(currency_code, data["balance"])


class Portfolio:
    """Портфель пользователя (набор кошельков)."""

    def __init__(self, user_id: int, wallets: Optional[Dict[str, Wallet]] = None):
        self._user_id = user_id
        self._wallets = wallets if wallets is not None else {}

    @property
    def user_id(self) -> int:
        return self._user_id

    @property
    def wallets(self) -> Dict[str, Wallet]:
        return self._wallets.copy()

    def add_currency(self, currency_code: str) -> None:
        code = currency_code.upper()
        if code not in self._wallets:
            self._wallets[code] = Wallet(code)

    def get_wallet(self, currency_code: str) -> Optional[Wallet]:
        return self._wallets.get(currency_code.upper())

    def get_total_value(self, base_currency: str = "USD", rate_provider=None) -> float:
        if rate_provider is None:
            return sum(
                w.balance for code, w in self._wallets.items() if code == base_currency
            )

        total = 0.0
        for code, wallet in self._wallets.items():
            if code == base_currency:
                total += wallet.balance
            else:
                rate = rate_provider(code, base_currency)
                total += wallet.balance * rate
        return total

    def to_dict(self) -> dict:
        return {
            "user_id": self._user_id,
            "wallets": {code: w.to_dict() for code, w in self._wallets.items()},
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Portfolio":
        wallets = {}
        for code, wdata in data.get("wallets", {}).items():
            wallets[code] = Wallet.from_dict(code, wdata)
        return cls(data["user_id"], wallets)

import hashlib

from .currencies import get_currency
from .exceptions import CurrencyNotFoundError


# ---------- Хеширование ----------
def hash_password(password: str, salt: str) -> str:
    """Возвращает хеш пароля с солью."""
    return hashlib.sha256((password + salt).encode()).hexdigest()


# ---------- Валидация ----------
def validate_amount(amount: str) -> float:
    """
    Проверяет, что строка может быть преобразована в положительное число.
    Возвращает float. Используется в CLI и в моделях.
    """
    try:
        value = float(amount)
    except ValueError:
        raise ValueError("Сумма должна быть числом")
    if value <= 0:
        raise ValueError("Сумма должна быть положительной")
    return value


def validate_currency_code(code: str) -> str:
    """
    Проверяет, что код валюты корректен и поддерживается.
    Возвращает нормализованный код (верхний регистр).
    """
    code = code.upper().strip()
    if not code:
        raise CurrencyNotFoundError(code)
    # Проверка существования через get_currency (может выбросить исключение)
    get_currency(code)  # для проверки
    return code

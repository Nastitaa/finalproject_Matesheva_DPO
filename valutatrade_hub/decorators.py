import functools
import logging
from typing import Callable, Optional

logger = logging.getLogger(__name__)


def log_action(action_name: Optional[str] = None, verbose: bool = False):
    """
    Декоратор для логирования вызова функций с контекстом.
    Используется в usecases для buy, sell, register, login.

    :param action_name: название действия (если не указано, берется имя функции)
    """

    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):

            act = action_name if action_name else func.__name__.upper()

            username = None
            #user_id = None

            if "username" in kwargs:
                username = kwargs["username"]
            elif len(args) > 1 and hasattr(args[1], "username"):
                username = args[1].username

            # Поля для логирования
            log_data = {
                "action": act,
                "username": username,
                "args": str(args),
                "kwargs": str(kwargs),
            }

            try:
                result = func(*args, **kwargs)
                log_data["result"] = "OK"
                if verbose:
                    pass
                logger.info(f"{log_data}")
                return result
            except Exception as e:
                log_data["result"] = "ERROR"
                log_data["error"] = str(e)
                logger.error(f"{log_data}", exc_info=True)
                raise 

        return wrapper

    return decorator

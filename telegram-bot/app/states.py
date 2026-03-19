"""FSM-состояния регистрации и оформления заказа."""

from aiogram.fsm.state import State, StatesGroup


class RegistrationState(StatesGroup):
    """Описывает шаг регистрации по контакту."""

    waiting_contact = State()


class CheckoutState(StatesGroup):
    """Описывает шаги оформления заказа."""

    waiting_full_name = State()
    waiting_address = State()
    waiting_confirmation = State()

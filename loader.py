from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from config import BOT_TOKEN

# Bot obyekti (HTML parse_mode bilan)
bot = Bot(
    token=BOT_TOKEN or "123456:dummy_token_for_tests",
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

# Dispatcher va FSM xotira ombori
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

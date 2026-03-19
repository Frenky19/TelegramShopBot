"""Inline роутер поиска по вопросам и ответам."""

from aiogram import Router
from aiogram.types import (
    InlineQuery,
    InlineQueryResultArticle,
    InputTextMessageContent,
)

from app.api import BackendClient
from app.constants import FAQ_INLINE_DESCRIPTION_LIMIT
from app.utils import truncate

router = Router(name='faq')


@router.inline_query()
async def inline_faq(query: InlineQuery, api: BackendClient) -> None:
    """Подбирает ответы для inline-запроса."""
    faqs = await api.get_faq(query.query)
    results = [
        InlineQueryResultArticle(
            id=str(item['id']),
            title=item['question'],
            description=truncate(
                item['answer'],
                FAQ_INLINE_DESCRIPTION_LIMIT,
            ),
            input_message_content=InputTextMessageContent(
                message_text=item['answer']
            ),
        )
        for item in faqs
    ]
    if not results:
        results = [
            InlineQueryResultArticle(
                id='empty',
                title='Ничего не найдено',
                description='Попробуйте изменить запрос.',
                input_message_content=InputTextMessageContent(
                    message_text='По запросу ничего не найдено.'
                ),
            )
        ]
    await query.answer(results, cache_time=0, is_personal=True)

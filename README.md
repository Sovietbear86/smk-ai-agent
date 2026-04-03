# SMK AI Agent MVP

Минимальный MVP AI-агента для SMK Performance Lab.

## Что умеет
- Принимать сообщение через FastAPI
- Определять intent
- Отвечать через простую KB из CSV
- Использовать LLM fallback, если KB не нашла ответ

## Быстрый старт
1. Создайте виртуальное окружение
2. Установите зависимости: `pip install -r requirements.txt`
3. Скопируйте `.env.example` в `.env`
4. Вставьте ваш OpenAI API key
5. Запустите: `uvicorn app.main:app --reload`
6. Откройте `http://127.0.0.1:8000/docs`

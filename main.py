import logging
import requests
import os
from telegram import Update, Bot, Voice, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, CallbackContext
from requests.exceptions import Timeout
from dotenv import load_dotenv

# Включаем отладочное логирование
logging.basicConfig(level=logging.DEBUG)

# Загружаем переменные окружения
#load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Глобальная переменная для хранения выбранной модели
selected_model = "nvidia/llama-3.1-nemotron-70b-instruct:free"

# Функция для получения списка моделей
def get_free_models():
    try:
        url = "https://openrouter.ai/api/v1/models"
        headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}"}
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            models = response.json().get("data", [])
            free_models = [m["id"] for m in models if ":free" in m["id"]]
            return free_models[:8]  # Ограничиваем 8 моделями
        else:
            logging.error(f"Ошибка получения моделей: {response.status_code} - {response.text}")
            return []
    except Exception as e:
        logging.error(f"Ошибка при запросе моделей: {e}", exc_info=True)
        return []

# Функция для отображения меню выбора модели
async def show_model_menu(update: Update, context: CallbackContext) -> None:
    models = get_free_models()
    if not models:
        await update.message.reply_text("Не удалось загрузить список моделей.")
        return
    
    keyboard = [[InlineKeyboardButton(model, callback_data=model)] for model in models]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Выберите модель для диалога:", reply_markup=reply_markup)

# Функция для обработки выбора модели
async def select_model(update: Update, context: CallbackContext) -> None:
    global selected_model
    query = update.callback_query
    await query.answer()
    selected_model = query.data
    await query.message.reply_text(f"Вы выбрали модель: {selected_model}\nТеперь можете начать диалог!")

# Функция для запроса к OpenRouter
def get_ai_response(user_message: str) -> str:
    try:
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}
        payload = {
            "model": selected_model,
            "messages": [{"role": "user", "content": user_message}]
        }
        
        response = requests.post(url, json=payload, headers=headers)
        logging.info(f"OpenRouter Response: {response.status_code} - {response.text}")
        
        if response.status_code == 200:
            return response.json().get("choices", [{}])[0].get("message", {}).get("content", "Ошибка в ответе ИИ")
        else:
            return f"Ошибка API: {response.status_code} - {response.text}"
    except Timeout:
        return "Запрос к API не был завершен вовремя. Попробуйте снова позже."
    except requests.exceptions.RequestException as e:
        return f"Ошибка при запросе: {e}"

# Функция для синтеза речи
def generate_voice(text: str) -> str:
    try:
        url = "https://api.openai.com/v1/audio/speech"
        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "tts-1",
            "input": text,
            "voice": "alloy"
        }
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            audio_path = "response.ogg"
            with open(audio_path, "wb") as f:
                f.write(response.content)
            return audio_path
        else:
            logging.error(f"Ошибка генерации речи: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        logging.error(f"Ошибка при создании голосового сообщения: {e}", exc_info=True)
        return None

# Функция для обработки текстовых сообщений
async def handle_message(update: Update, context: CallbackContext) -> None:
    user_message = update.message.text
    bot_response = get_ai_response(user_message)
    
    # Отправка текстового ответа
    await update.message.reply_text(bot_response)
    
    # Генерация голосового сообщения
    voice_file = generate_voice(bot_response)
    if voice_file:
        with open(voice_file, "rb") as voice:
            await update.message.reply_voice(voice)

# Запуск бота
def main():
    app = Application.builder().token(TELEGRAM_TOKEN).read_timeout(20).connect_timeout(20).build()
    app.add_handler(CommandHandler("start", show_model_menu))
    app.add_handler(CallbackQueryHandler(select_model))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("Бот запущен с ИИ и голосовыми сообщениями...")
    app.run_polling()

if __name__ == "__main__":
    main()

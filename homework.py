from http import HTTPStatus
import logging
import os
import sys
import time
import requests
from logging import StreamHandler
import exceptions
from exceptions import UnexpectedResponseException
import telegram
from telegram.ext import CommandHandler, Updater
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    logger.info(f'Сообщение: {message}. Oтправлено')
    return bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)


def wake_up(update, context):
    """Приветствующее слово."""
    chat = update.effective_chat
    name = update.message.chat.first_name
    context.bot.send_message(
        chat_id=chat.id,
        text=(
            'Привет, {}. Я тебе помогу узнать,'
            'на каком этапе проверки твоя домашка :)').format(name),
    )


def get_api_answer(current_timestamp):
    """Делает запрос к единственному эндпоинту API-сервиса."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        homework_statuses = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=params
        )
        if homework_statuses.status_code != HTTPStatus.OK:
            logger.error(
                f'Ошибка: неожиданный ответ {homework_statuses}.'
            )
            raise exceptions.UnexpectedResponseException(
                f'Ошибка: неожиданный ответ {homework_statuses}.'
            )
        return homework_statuses.json()
    except requests.exceptions.RequestException as e:
        logger.error(
            'Сбой в работе программы: ',
            f'Эндпоинт {ENDPOINT} недоступен.'
        )
        raise ("ValueError: {}".format(e))


def check_response(response):
    """Проверка полученных из API данных."""
    if response is None:
        logger.error('response пришел пустым.')
        raise UnexpectedResponseException
    if not isinstance(response, dict):
        logger.error('Некорректный тип данных response на входе')
        raise TypeError('Некорректный тип данных response на входе')
    if 'homeworks' not in response:
        logger.error('По ключу homeworks ничего нет')
        raise KeyError('Ошибка с ключем homeworks')
    if not response['homeworks']:
        return {}
    homework = response['homeworks']
    if not isinstance(homework, list):
        logger.error('По ключу homework данные не ввиде списка')
        raise TypeError('По ключу homework данные не ввиде списка')
    return homework


def parse_status(homework):
    """Получаем статус домашней работы."""
    if 'homework_name' not in homework:
        logger.error('По ключу homework_name ничего нет')
        raise KeyError('Ошибка с ключем homework_name')
    homework_name = homework['homework_name']
    if 'status' not in homework:
        logger.error('По ключу status ничего нет')
        raise KeyError('Ошибка с ключем status')
    homework_status = homework['status']
    verdict = HOMEWORK_STATUSES[homework_status]
    if verdict is None:
        raise KeyError('Недокументированный статус домашней работы, '
                       'обнаруженный в ответе API.')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяет доступность переменных окружения."""
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        raise KeyError('Ошибка окружения')
    updater = Updater(TELEGRAM_TOKEN)
    updater.dispatcher.add_handler(CommandHandler('start', wake_up))
    updater.start_polling()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    status_old = ''
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homework = check_response(response)
            if homework:
                status = parse_status(homework[0])
                if status_old != status:
                    send_message(bot, status)
                status_old = status
            current_timestamp = response.get('current_date')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            if status_old != message:
                send_message(bot, message)
            logger.error(f'Проблема с работой. Ошибка {error}')
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - модуль: %(module)s - функция: '
        '%(funcName)s - номер строки: %(lineno)d - %(message)s'
    )
    handler = StreamHandler(sys.stdout)
    logger.setLevel(logging.INFO)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    main()

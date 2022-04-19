import logging
import os
import sys
import time
import requests
import exceptions
import telegram
from telegram.ext import CommandHandler, Updater
from dotenv import load_dotenv

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}
PAYLOAD = {'from_date': 0}
HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logger = logging.getLogger()
streamHandler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter('%(asctime)s -  %(levelname)s - %(message)s')
streamHandler.setFormatter(formatter)
logger.addHandler(streamHandler)


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
        if homework_statuses.status_code // 100 != 2:
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
        raise ("Error: {}".format(e))


def check_response(response):
    """Проверка полученных из API данных."""
    result = response['homeworks']
    if result is None:
        logger.error('Отсутствует ожидаемый ключ')
        raise KeyError('Ключ "homeworks" не найден')
    if type(result) != list:
        raise TypeError('"result" не список')
    return result


def parse_status(homework):
    """Получаем статус домашней работы."""
    homework_name = homework['homework_name']
    homework_status = homework['status']
    verdict = HOMEWORK_STATUSES[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяет доступность переменных окружения."""
    tokens = {
        'Токен яндекс практикума': PRACTICUM_TOKEN,
        'Токен телеграм бота': TELEGRAM_TOKEN,
        'Id телеграм чата': TELEGRAM_CHAT_ID
    }
    if PRACTICUM_TOKEN and TELEGRAM_TOKEN and TELEGRAM_CHAT_ID is not None:
        logging.info('Все токены в норме')
        return True
    else:
        for name, token in tokens.items():
            if token is None:
                logging.critical(f'Ошибка в токене {name}')
        return False


def main():
    """Основная логика работы бота."""
    check_tokens()
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
            time.sleep(RETRY_TIME)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            print(message)
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()

import csv
from datetime import timedelta
from pydub import AudioSegment
from telegram import ReplyKeyboardMarkup, KeyboardButton, Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler
import speech_recognition as sr
import logging.config
from telegram.utils.request import Request
from Models import get_intent, get_response_by_intent, get_default_response, generate_answer, correct_spelling

TG_TOKEN = "1318466039:AAEW3iVZehtjCSB4BBcuB3jPsYb6XRgiPYE"
# Настройка логирования
logging.config.fileConfig('logging.conf')
logger = logging.getLogger("Your_assistant")

# Кол-во запросов к боту
count = 0
# Документы для отправки пользователю
standards = {'проверка ВКР': ['./standards/положение_о_порядке_проверки.pdf',
                              ' Положение о порядке проверки выпускных квалификационных работ.'],
             'вид деятельности': ['./standards/положение_по_виду_деятельности.pdf',
                                  ' Положение по виду деятельности о выпускной квалификационной работе.'],
             'список литературы': ['./standards/список_литературы.pdf',
                                   ' Общие требования и правила оформления списка литературы.']}
# Файлы с текстом ответа на команды бота
commands = {'mistakes': './commands/mistakes.txt',
            'need': './commands/need.txt',
            'help(start)': './commands/help(start).txt',
            'help(start)_commands': './commands/help(start)_commands.txt'}
button = {'need': 'Чек-лист', 'mistakes': 'Основные ошибки'}
statistics = {'requests': './reports/requests.csv'}
# Список со статистикой
data = {}
# Кнопки под сообщениями
LITERATURE_BUTTON = "literature"
ORDER_NORMCONTROL_BUTTON = "order_normcontrol"
TYPE_NORMCONTROL_BUTTON = "type_normcontrol"
TITLES = {
    LITERATURE_BUTTON: "Правила оформления списка литературы",
    ORDER_NORMCONTROL_BUTTON: "Положение о порядке проверки",
    TYPE_NORMCONTROL_BUTTON: "Положение по виду проверки",
}


# Клавиатура под сообщением с ответом бота
# Тема: список литературы
def literature_keyboard():
    keyboard = [
        [
            InlineKeyboardButton(TITLES[LITERATURE_BUTTON], callback_data=LITERATURE_BUTTON),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


# Клавиатура под сообщением с ответом бота
# Тема: нормконтроль
def normcontrol_keyboard():
    keyboard = [
        [
            InlineKeyboardButton(TITLES[ORDER_NORMCONTROL_BUTTON], callback_data=ORDER_NORMCONTROL_BUTTON),
        ],
        [
            InlineKeyboardButton(TITLES[TYPE_NORMCONTROL_BUTTON], callback_data=TYPE_NORMCONTROL_BUTTON),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


# Клавиатура с кнопками Чек-лист, Основные ошибки
def reply_markup_help():
    reply_markup = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="Чек-лист"),
                KeyboardButton(text="Основные ошибки"),
            ],
        ],
        resize_keyboard=True
    )
    return reply_markup


# Функция выбора клавиатуры в зависимости от ответа бота
def choose_keyboard(text):
    if text.find('Список литературы', 0, 18) != -1:
        return literature_keyboard()
    if text.find('Нормоконтроль', 0, 14) != -1:
        return normcontrol_keyboard()
    return reply_markup_help()


# Функция обработки нажатия клавиш
def callback_message(bot: Bot, update: Update):
    global query_data
    try:
        query = update.callback_query
        query_data = query.data
    except Exception as e:
        logger.info('Callback query: ' + str(e))
        update.message.reply_text(text='😔Извините, в данный момент нет возможности отправить документы.',
                                  reply_markup=reply_markup_help(), )
    else:
        logging.info('Callback query')
        if query_data == LITERATURE_BUTTON:
            send_document(bot, update, 'literature')
        if query_data == ORDER_NORMCONTROL_BUTTON:
            send_document(bot, update, 'order_normcontrol')
        if query_data == TYPE_NORMCONTROL_BUTTON:
            send_document(bot, update, 'type_normcontrol')


# Функция, определяющая способ ответа на сообщение пользователя
def get_answer(text):
    global count
    # NLU
    intent = get_intent(text)

    # Формирование ответа
    # Правила
    if intent:                  
        count += 1
        data['Model'] = 'rules'
        return get_response_by_intent(intent)

    # Генеративная модель
    response = generate_answer(text)
    if response:
        count += 1
        data['Model'] = 'generative model'
        return response

    # Заглушка
    count += 1
    data['Model'] = 'stub'
    return get_default_response()


# Команда /help и /start для бота
def user_help(bot: Bot, update: Update):
    try:
        with open(commands['help(start)'], 'r', encoding='utf-8') as file:
            update.message.reply_text(text=file.read(), reply_markup=reply_markup_help(), )
        with open(commands['help(start)_commands'], 'r', encoding='utf-8') as file:
            bot.send_message(chat_id=update.message.chat_id, text=file.read(), reply_markup=reply_markup_help(), )
    except Exception as e:
        logger.info('Command help(start): ' + str(e))
        update.message.reply_text(text='😔Извините, текущая команда в данный момент недоступна.', reply_markup=reply_markup_help(), )


# Команда /standards для бота
def user_standards(bot: Bot, update: Update):
    logger.info("Sending documents")
    try:
        for value in standards.values():
            with open(value[0], 'rb') as file:
                bot.send_document(chat_id=update.message.chat_id, document=file,
                                  caption=value[1])
    except Exception as e:
        logger.info('Command standards: ' + str(e))
        update.message.reply_text(text='😔Извините, текущая команда в данный момент недоступна.', reply_markup=reply_markup_help(), )


# Команда /mistakes для бота
def user_mistakes(bot: Bot, update: Update):
    try:
        with open(commands['mistakes'], 'r', encoding='utf-8') as file:
            update.message.reply_text(text=file.read(), reply_markup=reply_markup_help(), )
    except Exception as e:
        logger.info('Command mistakes: ' + str(e))
        update.message.reply_text(text='😔Извините, текущая команда в данный момент недоступна.', reply_markup=reply_markup_help(), )


# Команда /need для бота
def user_need(bot: Bot, update: Update):
    try:
        with open(commands['need'], 'r', encoding='utf8') as file:
            update.message.reply_text(text=file.read(), reply_markup=reply_markup_help(), )
    except Exception as e:
        logger.info('Command need: ' + str(e))
        update.message.reply_text(text='😔Извините, текущая команда в данный момент недоступна.', reply_markup=reply_markup_help(), )


# Сохранение статистики по запросам пользователей
def save_statistics(data):
    fieldnames = ['Number', 'Chat id', 'Date', 'Type message', 'Question', 'Answer', 'Model']
    try:
        with open(statistics['requests'], "a", encoding='utf-8') as csv_file:
            file_writer = csv.DictWriter(csv_file, delimiter=";", fieldnames=fieldnames, lineterminator="\r")
            file_writer.writerow(data)
    except Exception as e:
        logger.info('Save statistics: ' + str(e))


# Отправка документов пользователю
def send_document(bot: Bot, update: Update, text):
    try:
        if text == 'literature':
            logger.info("Sending document(-s)")
            with open(standards['список литературы'][0], 'rb') as file:
                bot.send_document(chat_id=update.callback_query.message.chat_id, document=file, caption=standards['список литературы'][1])
        if text == 'order_normcontrol':
            logger.info("Sending document(-s)")
            with open(standards['проверка ВКР'][0], 'rb') as file:
                bot.send_document(chat_id=update.callback_query.message.chat_id, document=file, caption=standards['проверка ВКР'][1])
        if text == 'type_normcontrol':
            logger.info("Sending document(-s)")
            with open(standards['вид деятельности'][0], 'rb') as file:
                bot.send_document(chat_id=update.callback_query.message.chat_id, document=file, caption=standards['вид деятельности'][1])
    except Exception as e:
        logger.info('Send document(-s): ' + str(e))
        update.message.reply_text(text='😔Извините, в данный момент нет возможности отправить документы.', reply_markup=reply_markup_help(), )


def bot_answer(bot: Bot, update: Update, text):
    text = correct_spelling(text)
    answer = get_answer(text)
    data['Number'] = count
    data['Chat id'] = str(update.message.from_user.id)
    data['Date'] = str(update.message.date + timedelta(hours=3))
    data['Question'] = text
    data['Answer'] = answer
    save_statistics(data)
    update.message.reply_text(answer, reply_markup=choose_keyboard(answer), )


# Ответ на текстовое сообщение
def text_message(bot: Bot, update: Update):
    data['Type message'] = 'text'
    text = update.message.text
    if text == button['need']:
        user_need(bot, update)
    elif text == button['mistakes']:
        user_mistakes(bot, update)
    else:
        bot_answer(bot, update, text)


# Ответ на голосовое сообщение
def audio_message(bot: Bot, update: Update):
    data['Type message'] = 'audio'
    try:
        recognizer = sr.Recognizer()
        fileID = update.message.voice.file_id
        file = bot.get_file(fileID)
        file.download('audio.ogg')
        sound = AudioSegment.from_ogg('audio.ogg')
        sound.export('audio.wav', format="wav")
        try:
            with sr.WavFile('audio.wav') as source:
                audio = recognizer.record(source)
                text = recognizer.recognize_google(audio, language='ru_RU').lower()
                bot_answer(bot, update, text)
        except sr.UnknownValueError:
            update.message.reply_text('Извините, не понял что вы сказали.')
    except Exception as e:
        logger.info('Audio message: ' + str(e))
        update.message.reply_text(text='😔Извините, в данный момент нет возможности прослушать голосовое сообщение.', reply_markup=reply_markup_help(), )


def main():
    logger.info("Launch chat bot")
    # Настройка бота
    req = Request(
        connect_timeout=0.5,
    )
    bot = Bot(
        token=TG_TOKEN,
        request=req,
    )
    updater = Updater(
        bot=bot,
        use_context=False
    )

    # Проверка, что бот корректно подключился к Telegram API
    info = bot.get_me()
    logger.info(f'Bot info: {info}')

    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", user_help))
    dp.add_handler(CommandHandler("help", user_help))
    dp.add_handler(CommandHandler("standards", user_standards))
    dp.add_handler(CommandHandler("mistakes", user_mistakes))
    dp.add_handler(CommandHandler("need", user_need))
    dp.add_handler(MessageHandler(Filters.voice & ~Filters.command, audio_message))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, text_message))
    dp.add_handler(CallbackQueryHandler(callback=callback_message))
    # dp.add_handler(MessageHandler(Filters.status_update.new_chat_members, user_help))

    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()

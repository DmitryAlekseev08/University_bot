import csv
from datetime import timedelta
from pydub import AudioSegment
from telegram import ReplyKeyboardMarkup, KeyboardButton, Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler, ConversationHandler
import speech_recognition as sr
import logging.config
from telegram.utils.request import Request
from Models import get_intent, get_response_by_intent, get_default_response, match, correct_spelling, remove_punctuation, form_of_word
#from Autofill import conv_fill_title

TG_TOKEN = "1318466039:AAEW3iVZehtjCSB4BBcuB3jPsYb6XRgiPYA"
# Logging Settings
logging.config.fileConfig('logging.conf')
logger = logging.getLogger("Normobot")

# Number of requests to the bot
count = 0
# Documents to send to the user
standards = {'проверка ВКР': ['./standards/положение_о_порядке_проверки.pdf',
                              ' Положение о порядке проверки выпускных квалификационных работ.'],
             'вид деятельности': ['./standards/положение_по_виду_деятельности.pdf',
                                  ' Положение по виду деятельности о выпускной квалификационной работе.'],
             'список литературы': ['./standards/список_литературы.pdf',
                                   ' Общие требования и правила оформления списка литературы.']}
# Files with the text of responses to bot commands
commands = {'mistakes': './commands/mistakes.txt',
            'need': './commands/need.txt',
            'help(start)': './commands/help(start).txt',
            'help(start)_commands': './commands/help(start)_commands.txt'}

# Buttons located next to the keyboard
button = {'need': 'Чек-лист', 'mistakes': 'Основные ошибки'}
# Buttons under messages
LITERATURE_BUTTON = "literature"
ORDER_NORMCONTROL_BUTTON = "order_normcontrol"
TYPE_NORMCONTROL_BUTTON = "type_normcontrol"
TITLES = {
    LITERATURE_BUTTON: "Правила оформления списка литературы",
    ORDER_NORMCONTROL_BUTTON: "Положение о порядке проверки",
    TYPE_NORMCONTROL_BUTTON: "Положение по виду деятельности",
}
# Constants for ConversationHandler
CHECK, CHAT_ID, TEXT_MESSAGE = range(3)

# Chat admin id
ADMIN_CHAT_ID = ''
# Files available in admin mode
admin_files = {'logs': ['./reports/logs.log', 'Файл с записями о событиях программы.'],
               'stats': ['./reports/requests.csv', 'Файл с записями о запросах пользователей.'],
               'password': './reports/password.txt',
               'commands': './commands/admin_commands.txt'}
# List with statistics
data = {}
# File with query statistics
statistics = {'requests': './reports/requests.csv'}
# Information required to send a message on behalf of the bot
message = {'chat_id': '',
           'text': ''}


# Keyboard under the message with the bot's response
# Topic: literature
def literature_keyboard():
    keyboard = [
        [
            InlineKeyboardButton(TITLES[LITERATURE_BUTTON], callback_data=LITERATURE_BUTTON),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


# Keyboard under the message with the bot's response
# Topic: work
def work_keyboard():
    keyboard = [
        [
            InlineKeyboardButton(TITLES[TYPE_NORMCONTROL_BUTTON], callback_data=TYPE_NORMCONTROL_BUTTON),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


# Keyboard under the message with the bot's response
# Topic: normocontrol
def normocontrol_keyboard():
    keyboard = [
        [
            InlineKeyboardButton(TITLES[ORDER_NORMCONTROL_BUTTON], callback_data=ORDER_NORMCONTROL_BUTTON),
        ],
        [
            InlineKeyboardButton(TITLES[TYPE_NORMCONTROL_BUTTON], callback_data=TYPE_NORMCONTROL_BUTTON),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


# Keyboard with buttons: Чек-лист, Основные ошибки
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


# Keyboard selection function depending on the bot's response
def choose_keyboard(text):
    if text.find('Список литературы', 0, 18) != -1:
        return literature_keyboard()
    if text.find('Нормоконтроль', 0, 14) != -1:
        return normocontrol_keyboard()
    if text.find('Работа', 0, 7) != -1:
        return work_keyboard()
    return reply_markup_help()


# Keystroke processing function
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
        logging.info('Callback query: ' + query_data)
        if query_data == LITERATURE_BUTTON:
            send_document(bot, update, 'literature')
        if query_data == ORDER_NORMCONTROL_BUTTON:
            send_document(bot, update, 'order_normcontrol')
        if query_data == TYPE_NORMCONTROL_BUTTON:
            send_document(bot, update, 'type_normcontrol')


# Function that determines how to respond to the user's message
def get_answer(text):
    global count
    # NLU
    intent = get_intent(text)

    # Ml model
    if intent:                  
        count += 1
        data['Model'] = 'ML model'
        return get_response_by_intent(intent)

    # Algorithm based on the Levenshtein distance
    response = match(text)
    if response:
        count += 1
        data['Model'] = 'Levenshtein distance'
        return response

    # Stubs
    count += 1
    data['Model'] = 'Stub'
    return get_default_response()


# Commands /help и /start
def user_help(bot: Bot, update: Update):
    logger.info("Commands help or start")
    try:
        with open(commands['help(start)'], 'r', encoding='utf-8') as file:
            update.message.reply_text(text=file.read(), reply_markup=reply_markup_help(), )
        with open(commands['help(start)_commands'], 'r', encoding='utf-8') as file:
            bot.send_message(chat_id=update.message.chat_id, text=file.read(), reply_markup=reply_markup_help(), )
    except Exception as e:
        logger.info('Command help(start): ' + str(e))
        update.message.reply_text(text='😔Извините, текущая команда в данный момент недоступна.', reply_markup=reply_markup_help(), )


# Commands /standards
def user_standards(bot: Bot, update: Update):
    logger.info("Send standards")
    try:
        for value in standards.values():
            with open(value[0], 'rb') as file:
                bot.send_document(chat_id=update.message.chat_id, document=file,
                                  caption=value[1])
    except Exception as e:
        logger.info('Command standards: ' + str(e))
        update.message.reply_text(text='😔Извините, текущая команда в данный момент недоступна.', reply_markup=reply_markup_help(), )


# Commands /mistakes
def user_mistakes(bot: Bot, update: Update):
    logger.info("Command mistakes")
    try:
        with open(commands['mistakes'], 'r', encoding='utf-8') as file:
            update.message.reply_text(text=file.read(), reply_markup=reply_markup_help(), )
    except Exception as e:
        logger.info('Command mistakes: ' + str(e))
        update.message.reply_text(text='😔Извините, текущая команда в данный момент недоступна.', reply_markup=reply_markup_help(), )


# Commands /need
def user_need(bot: Bot, update: Update):
    logger.info("Command need")
    try:
        with open(commands['need'], 'r', encoding='utf8') as file:
            update.message.reply_text(text=file.read(), reply_markup=reply_markup_help(), )
    except Exception as e:
        logger.info('Command need: ' + str(e))
        update.message.reply_text(text='😔Извините, текущая команда в данный момент недоступна.', reply_markup=reply_markup_help(), )


# Log in to Admin mode
def admin_entry(bot: Bot, update: Update):
    logger.info("Attempt to log in to admin mode")
    if ADMIN_CHAT_ID == '':
        update.message.reply_text(text='Введите пароль.', reply_markup=None,)
        return CHECK
    else:
        update.message.reply_text(text='Кто-то уже зашёл как администратор.🤷‍♂️', reply_markup=reply_markup_help(), )
        return ConversationHandler.END


# Authentication
def check_user(bot: Bot, update: Update):
    global ADMIN_CHAT_ID
    global admin_password
    try:
        with open(admin_files['password'], 'r', encoding='utf8') as file:
            admin_password = file.read()
    except Exception as e:
        logger.info('Read admin password: ' + str(e))
        update.message.reply_text(text='😔Извините, в данный момент нет возможности провести аутентификацию.', reply_markup=None,)
    if update.message.text == admin_password:
        ADMIN_CHAT_ID = update.message.chat_id
        logger.info(f'Enter admin, chat_id:{ADMIN_CHAT_ID}')
        try:
            with open(admin_files['commands'], 'r', encoding='utf-8') as file:
                update.message.reply_text(text=file.read(), reply_markup=None )
        except Exception as e:
            logger.info('Admin commands: ' + str(e))
            update.message.reply_text(text='😔Извините, в данный момент нет возможности провести аутентификацию.',
                                      reply_markup=reply_markup_help(), )
    else:
        update.message.reply_text(text='Вы ввели неверный пароль.', reply_markup=reply_markup_help(),)
    return ConversationHandler.END


# Send the log file
def admin_logs(bot: Bot, update: Update):
    if update.message.chat_id == ADMIN_CHAT_ID:
        logger.info("Send logs")
        try:
            with open(admin_files['logs'][0], 'rb') as file:
                bot.send_document(chat_id=update.message.chat_id, document=file,
                                  caption=admin_files['logs'][1])
        except Exception as e:
            logger.info('Send logs: ' + str(e))
            update.message.reply_text(text='😔Извините, в данный момент нет возможности отправить файл.', reply_markup=None,)


# Send statistics on user requests
def admin_stats(bot: Bot, update: Update):
    if update.message.chat_id == ADMIN_CHAT_ID:
        logger.info("Send stats")
        try:
            with open(admin_files['stats'][0], 'rb') as file:
                bot.send_document(chat_id=update.message.chat_id, document=file,
                                  caption=admin_files['stats'][1])
        except Exception as e:
            logger.info('Send stats: ' + str(e))
            update.message.reply_text(text='😔Извините, в данный момент нет возможности отправить файл.', reply_markup=None,)


# Exit administrator Mode
def admin_exit(bot: Bot, update: Update):
    global ADMIN_CHAT_ID
    if update.message.chat_id == ADMIN_CHAT_ID:
        logger.info(f'Exit admin, chat_id:{ADMIN_CHAT_ID}')
        ADMIN_CHAT_ID = ''
        update.message.reply_text(text='Вы вышли из режима администратора чат-бота.🤓', reply_markup=reply_markup_help(),)


# Enter the chat_id to send the message
def enter_chat_id(bot: Bot, update: Update):
    logger.info("Send message to user from admin")
    if update.message.chat_id == ADMIN_CHAT_ID:
        update.message.reply_text(text='Введите chat_id.')
        return CHAT_ID
    else:
        return ConversationHandler.END


# Enter the text of the message to send to the user
def enter_text_message(bot: Bot, update: Update):
    message['chat_id'] = update.message.text
    update.message.reply_text(text='Введите текст сообщения.')
    return TEXT_MESSAGE


# Send a message to the user
def send_message(bot: Bot, update: Update):
    message['text'] = update.message.text
    logger.info("Send message to user from admin, chat_id: " + message['chat_id'] + ', text: ' + message['text'])
    try:
        bot.send_message(chat_id=message['chat_id'], text=message['text'])
    except Exception as e:
        logger.info('Send message to user: ' + str(e))
        update.message.reply_text(text='😔Не получилось отправить сообщение.',
                                  reply_markup=None, )
    else:
        update.message.reply_text(text='Сообщение отправлено.😉', reply_markup=None, )
        logger.info('Send message to user.')
    message['chat_id'] = ''
    message['text'] = ''
    return ConversationHandler.END


# Save statistics on user requests
def save_statistics(data):
    logger.info("Save statistics")
    fieldnames = ['Number', 'Chat id', 'Date', 'Type message', 'Question', 'Answer', 'Model']
    try:
        with open(statistics['requests'], "a", encoding='utf-8') as csv_file:
            file_writer = csv.DictWriter(csv_file, delimiter=",", fieldnames=fieldnames, lineterminator="\r")
            file_writer.writerow(data)
    except Exception as e:
        logger.info('Save statistics: ' + str(e))


# Send documents to the user
def send_document(bot: Bot, update: Update, text):
    try:
        if text == 'literature':
            logger.info("Send document(-s): " + standards['список литературы'][1])
            with open(standards['список литературы'][0], 'rb') as file:
                bot.send_document(chat_id=update.callback_query.message.chat_id, document=file, caption=standards['список литературы'][1])
        if text == 'order_normcontrol':
            logger.info("Send document(-s): " + standards['проверка ВКР'][1])
            with open(standards['проверка ВКР'][0], 'rb') as file:
                bot.send_document(chat_id=update.callback_query.message.chat_id, document=file, caption=standards['проверка ВКР'][1])
        if text == 'type_normcontrol':
            logger.info("Send document(-s): " + standards['вид деятельности'][1])
            with open(standards['вид деятельности'][0], 'rb') as file:
                bot.send_document(chat_id=update.callback_query.message.chat_id, document=file, caption=standards['вид деятельности'][1])
    except Exception as e:
        logger.info('Send document(-s): ' + str(e))
        update.message.reply_text(text='😔Извините, в данный момент нет возможности отправить документы.', reply_markup=reply_markup_help(), )


def bot_answer(bot: Bot, update: Update, text):
    text = correct_spelling(text)
    text = remove_punctuation(text)
    text = form_of_word(text)
    answer = get_answer(text)
    data['Number'] = count
    data['Chat id'] = str(update.message.from_user.id)
    data['Date'] = str(update.message.date + timedelta(hours=3))
    data['Question'] = repr(text)
    data['Answer'] = repr(answer)
    save_statistics(data)
    update.message.reply_text(answer, reply_markup=choose_keyboard(answer), )


# Reply to the text message
def text_message(bot: Bot, update: Update):
    data['Type message'] = 'text'
    text = update.message.text
    if text == button['need']:
        user_need(bot, update)
    elif text == button['mistakes']:
        user_mistakes(bot, update)
    else:
        bot_answer(bot, update, text)


# Reply to a voice message
def audio_message(bot: Bot, update: Update):
    data['Type message'] = 'audio'
    logger.info('Voice message processing')
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
        logger.info('Voice message: ' + str(e))
        update.message.reply_text(text='😔Извините, в данный момент нет возможности прослушать голосовое сообщение.', reply_markup=reply_markup_help(), )


def main():
    logger.info("Launch chat bot")
    # Configure the bot
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

    # Check that the bot has correctly connected to the Telegram API
    info = bot.get_me()
    logger.info(f'Bot info: {info}')

    # Authentication
    authentication = ConversationHandler(
        # Entry point
        entry_points=[
            CommandHandler('admin', admin_entry),
        ],
        # Dictionary of states
        states={
            CHECK: [
                MessageHandler(Filters.all, check_user),
            ],
        },
        fallbacks=[],
    )

    # Send the message to the user
    send_message_to_user = ConversationHandler(
        # Entry point
        entry_points=[
            CommandHandler('message', enter_chat_id),
        ],
        # Dictionary of states
        states={
            CHAT_ID: [
                MessageHandler(Filters.all, enter_text_message),
            ],
            TEXT_MESSAGE: [
                MessageHandler(Filters.all, send_message),
            ]
        },
        fallbacks=[],
    )

    dp = updater.dispatcher
    dp.add_handler(authentication)
    dp.add_handler(send_message_to_user)
    #dp.add_handler(conv_fill_title())
    dp.add_handler(CommandHandler("start", user_help))
    dp.add_handler(CommandHandler("help", user_help))
    dp.add_handler(CommandHandler("standards", user_standards))
    dp.add_handler(CommandHandler("mistakes", user_mistakes))
    dp.add_handler(CommandHandler("need", user_need))
    dp.add_handler(MessageHandler(Filters.voice & ~Filters.command, audio_message))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, text_message))
    dp.add_handler(CallbackQueryHandler(callback=callback_message))
    dp.add_handler(CommandHandler("logs", admin_logs))
    dp.add_handler(CommandHandler("stats", admin_stats))
    dp.add_handler(CommandHandler("exit", admin_exit))
    # dp.add_handler(MessageHandler(Filters.status_update.new_chat_members, user_help))

    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()

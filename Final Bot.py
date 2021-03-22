import random
from nltk import word_tokenize, edit_distance
from pydub import AudioSegment
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.linear_model import LogisticRegression
from pyaspeller import YandexSpeller
from pymystem3 import Mystem
from telegram import ReplyKeyboardMarkup, KeyboardButton, Bot, Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
import speech_recognition as sr
import logging.config
from telegram.utils.request import Request
from Config import BOT_CONFIG

TG_TOKEN = "1318466039:AAEW3iVZehtjCSB4BBcuB3jPsYb6XRgiPYE"
# Настройка логирования
logging.config.fileConfig('logging.conf')
logger = logging.getLogger("Your_assistant")

stats = {'intent': 0, 'generative': 0, 'stub': 0}


# Подготовка текста
def correct_spelling(text):
    speller = YandexSpeller()
    changes = {change['word']: change['s'][0] for change in speller.spell(text)}
    for word, suggestion in changes.items():
        text = text.replace(word, suggestion)
    return text


# Преобразование слов к начальной форме
def form_of_word(text):
    m3 = Mystem()
    text = ''.join(m3.lemmatize(text))
    return text


# Датасет для генеративной модели
with open('dialogues.txt', encoding='utf-8') as f:
    content = f.read()

dialogues = []  # [[Q, A], ...]

# Разделение диалогов
for dialogue_text in content.split('\n\n'):
    replicas = dialogue_text.split('\n')
    if len(replicas) >= 2:
        # Берутся только первые две реплики
        replicas = replicas[:2]
        # Убираются " -" в начаое каждой строки
        replicas = [replica[2:] for replica in replicas]
        replicas[0] = replicas[0].lower().strip()
        replicas[0] = form_of_word(replicas[0])
        if replicas[0]:
            dialogues.append(tuple(replicas))

# Избавление от повторов
dialogues = list(set(dialogues))

qa_dataset = {}

# Разбиение диалогов на словарь токенов(текстовых единиц), в котором ключи - это слова, а значения - это диалоги,
# содержащие эти слова Это поможет ускорить выполнение программы
alphabet = 'йцукенгшщзхъфывапролджэёячсмитьбю'
for question, answer in dialogues:
    tokens = word_tokenize(question)
    words = [token for token in tokens if any(char in token for char in alphabet)]
    for word in words:
        if word not in qa_dataset:
            qa_dataset[word] = []
        qa_dataset[word].append((question, answer))

dataset = []  # [[x, y], [example, intent], ...]

for intent, intent_data in BOT_CONFIG['intents'].items():
    for example in intent_data['examples']:
        dataset.append([example, intent])

X_text = [x for x, y in dataset]
y = [y for x, y in dataset]

# Векторизация
vectorizer = CountVectorizer()
X = vectorizer.fit_transform(X_text)

# Классификация
clf = LogisticRegression()
clf.fit(X, y)


# Классификация намерений
def get_intent(text):
    logger.info("Rules")
    vector = vectorizer.transform([text])
    winner = clf.predict(vector)[0]
    index = list(clf.classes_).index(winner)
    proba = clf.predict_proba(vector)[0][index]
    if proba > 0.3:
        return winner


# Выбор ответа для чат-бота
def get_response_by_intent(intent):
    candidates = BOT_CONFIG['intents'][intent]['responses']
    return random.choice(candidates)


# Генеративная модель
def generate_answer(text):
    logger.info("Generate model")
    text = text.lower()
    text = form_of_word(text)
    tokens = word_tokenize(text)
    words = [token for token in tokens if any(char in token for char in alphabet)]
    for word in words:
        if word in qa_dataset:
            for question, answer in qa_dataset[word]:
                # Если текст пользователя и утверждение(вопрос) в словаре сильно отличаются по длине, то нет смысла применять
                # Расстояние Левенштейна
                if abs(len(text) - len(question)) / len(question) < 0.2:
                    # Расстояние Левенштейна
                    distance = edit_distance(text, question)
                    if distance / len(question) < 0.2:
                        return answer


# Заглушка
def get_default_response():
    logger.info("Default answer")
    candidates = BOT_CONFIG['failure_phrases']
    return random.choice(candidates)


# Функция, определяющая способ ответа на сообщение пользователя
def get_answer(text):
    # NLU
    intent = get_intent(text)

    # Формирование ответа

    # Правила
    if intent:
        stats['intent'] += 1
        return get_response_by_intent(intent)

    # Генеративная модель
    response = generate_answer(text)
    if response:
        stats['generative'] += 1
        return response

    # Заглушка
    stats['stub'] += 1
    return get_default_response()


# Команда /help и /start для бота
def user_help(bot: Bot, update: Update):
    update.message.reply_text('  Приветствую!👋\n' +
                              '  Тематика данного бота:\n'
                              '‣ нормконтроль (что из себя представляет, что необходимо иметь при себе);\n'
                              '‣ комплектация пояснительной записки (титульный лист, задание к ВКР, аннотация, '
                              'содержание, сама работа, списко литературы, приложения), необходимые подписи;\n'
                              '‣ компакт-диски (необходимое количество, информация для записи на диск);\n'
                              '‣ графическая часть и раздаточный материал (что представляет из себя, необходимые '
                              'подписи);\n'
                              '‣ проверка на антиплагиат (в чём заключается, справка об антиплагиате);\n'
                              '‣ отзыв руководителя (кем составляется);\n'
                              '‣ рецензия (кем готовится, необходимые подписи и печати);\n'
                              '‣ что необходимо сделать после прохождения нормконтроля.\n'
                              'Задавай интересующие тебя вопросы.😉', reply_markup=reply_markup_help(), )


# Клавиатура с кнопкой /help
def reply_markup_help():
    reply_markup = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="/help"),
            ],
        ],
        resize_keyboard=True
    )
    return reply_markup


def bot_answer(bot: Bot, update: Update, text):
    text = correct_spelling(text)
    answer = get_answer(text)
    count = sum(stats.values())
    print(f'Question: {update.message.text}  Answer: {answer}')
    print(f'{stats["intent"] / count * 100:.2f} intent, '
          f'{stats["generative"] / count * 100:.2f} generative, '
          f'{stats["stub"] / count * 100:.2f} stub, '
          f'count={count}')
    print()
    update.message.reply_text(answer, reply_markup=reply_markup_help(), )
    # with open('Dataset.txt', 'rb') as file:
    #    bot.send_document(update.message.chat_id, file)


# Ответ на текстовое сообщение
def text_message(bot: Bot, update: Update):
    bot_answer(bot, update, update.message.text)


# Ответ на голосовое сообщение
def audio_message(bot: Bot, update: Update):
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
    dp.add_handler(MessageHandler(Filters.voice & ~Filters.command, audio_message))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, text_message))

    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()

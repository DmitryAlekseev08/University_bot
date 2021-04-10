from nltk import word_tokenize, edit_distance
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.linear_model import LogisticRegression
from pyaspeller import YandexSpeller
from pymystem3 import Mystem
import random
from Config import BOT_CONFIG


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
    candidates = BOT_CONFIG['failure_phrases']
    return random.choice(candidates)
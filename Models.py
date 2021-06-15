from sklearn.feature_extraction.text import CountVectorizer
from sklearn.model_selection import train_test_split
from sklearn.svm import LinearSVC
from pyaspeller import YandexSpeller
from pymystem3 import Mystem
import random
import string
from nltk import word_tokenize, edit_distance
# Dataset file
from Config import BOT_CONFIG


# Correction of grammatical errors
def correct_spelling(text):
    speller = YandexSpeller()
    changes = {change['word']: change['s'][0] for change in speller.spell(text)}
    for word, suggestion in changes.items():
        text = text.replace(word, suggestion)
    return text


# Lemmatization
def form_of_word(text):
    m3 = Mystem()
    text = ''.join(m3.lemmatize(text))
    return text


# Removing punctuation characters
def remove_punctuation(text):
    translator = str.maketrans('', '', string.punctuation)
    return text.translate(translator)


# Processing a dataset
dataset = []  # [[x, y], [example, intent], ...]
for intent, intent_data in BOT_CONFIG['intents'].items():
    for ex in range(len(intent_data['examples'])):
        intent_data['examples'][ex] = remove_punctuation(intent_data['examples'][ex])
        intent_data['examples'][ex] = form_of_word(intent_data['examples'][ex])
        dataset.append([intent_data['examples'][ex], intent])


# Dataset for the model based on the Levenshtein distance
dialogues = []  # [[Q, A], ...]
replicas = ['', '']
for intent in BOT_CONFIG['intents'].values():
    for example in intent['examples']:
        for response in intent['responses']:
            replicas[0] = example
            replicas[1] = response
            dialogues.append(tuple(replicas))
qa_dataset = {}


# Splitting dialogs into a dictionary of tokens (text units), in which keys are words and values are dialogs,
# containing these words. This will help speed up the execution of the program
alphabet = 'йцукенгшщзхъфывапролджэёячсмитьбю'
for question, answer in dialogues:
    tokens = word_tokenize(question)
    words = [token for token in tokens if any(char in token for char in alphabet)]
    for word in words:
        if word not in qa_dataset:
            qa_dataset[word] = []
        qa_dataset[word].append((question, answer))


X_text = [x for x, y in dataset]
y = [y for x, y in dataset]

# Vectorizer
vectorizer = CountVectorizer(analyzer='char_wb', ngram_range=(2,3), max_df=0.85)
X = vectorizer.fit_transform(X_text)

# Classifier
clf = LinearSVC(C=1.0, class_weight='balanced', max_iter=100)
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.33, stratify=y)
clf.fit(X_train.toarray(), y_train)


# Classification of user intentions
def get_intent(text):
    vector = vectorizer.transform([text])
    winner = clf.predict(vector)[0]
    return winner


# Selecting a response for a chatbot
def get_response_by_intent(intent):
    candidates = BOT_CONFIG['intents'][intent]['responses']
    return random.choice(candidates)


# Algorithm based on the Levenshtein distance
def match(text):
    tokens = word_tokenize(text)
    words = [token for token in tokens if any(char in token for char in alphabet)]
    for word in words:
        if word in qa_dataset:
            for question, answer in qa_dataset[word]:
                # If the user's text and the statement (question) in the dictionary are very different in length, then it makes no sense to apply
                # Levenshtein distance
                if abs(len(text) - len(question)) / len(question) < 0.2:
                    # Levenshtein distance
                    distance = edit_distance(text, question)
                    if distance / len(question) < 0.2:
                        return random.choice(answer)


# Stubs
def get_default_response():
    candidates = BOT_CONFIG['failure_phrases']
    return random.choice(candidates)

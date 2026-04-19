import pickle
from textblob import TextBlob
from transformers import pipeline
import spacy
from collections import Counter

# 🔥 Load spaCy
nlp = spacy.load("en_core_web_sm")

# 🔥 Load ML model
model = pickle.load(open("model.pkl", "rb"))
vectorizer = pickle.load(open("vectorizer.pkl", "rb"))

# 🔥 Load Toxicity Model
toxicity_model = pipeline(
    "text-classification",
    model="cardiffnlp/twitter-roberta-base-offensive"
)

# Keyword lists for lexicon scoring (used with negation + emoji paths)
positive_words = {
    "good", "great", "love", "loved", "loves", "excellent", "happy", "amazing", "best",
    "wonderful", "fantastic", "nice", "beautiful", "perfect", "awesome", "brilliant",
    "joy", "lovely", "pleased", "glad", "delighted", "superb", "outstanding", "fine",
    "incredible", "marvelous", "spectacular", "splendid", "terrific", "fabulous", "like",
    "liked", "enjoy", "enjoyed", "thanks", "thank",
}
negative_words = {
    "bad", "terrible", "hate", "hated", "awful", "worst", "horrible", "sad", "angry",
    "poor", "ugly", "pathetic", "disgusting", "nasty", "disappointing", "gross", "fail",
    "failed", "sucks", "suck", "hateful", "dire", "grim", "vile", "dislike", "disliked",
    "annoying", "frustrating", "depressing", "boring", "worse",
}

sarcasm_indicators = [
    "🙄", "yeah right", "as if", "wow", "great... not", "not really", "uh huh"
]

negation_words = ["not", "no", "never", "n't"]

positive_emojis = ["🔥", "💯", "❤️", "😍", "🙌", "👏", "🐐", "✨", "🥰", "💪", "😎", "🤩"]
negative_emojis = ["🤮", "💩", "🗑️", "🤡", "😡", "🤬", "👎", "🤢", "🤦", "🖕", "💔", "🥱"]


# 🔥 STEP 0: TEXT PREPROCESSING (NEW)
def preprocess_text(text):
    doc = nlp(text.lower())

    tokens = [
        token.text for token in doc
        if not token.is_stop and token.is_alpha
    ]

    return " ".join(tokens)


# 🔥 STEP EXTRA: KEYWORD EXTRACTION (NEW)
def extract_keywords(text):
    doc = nlp(text)

    keywords = [
        token.text.lower()
        for token in doc
        if token.pos_ in ["NOUN", "PROPN"]
    ]

    return keywords


def get_sentiment(text):
    original_text = str(text)

    # 🔥 NEW: Preprocess
    clean_text = preprocess_text(original_text)
    text = clean_text.lower()

    # 🚨 STEP 1: Toxicity
    try:
        tox = toxicity_model(original_text)[0]
        if ("OFFENSIVE" in tox['label'] or "LABEL_1" in tox['label']) and tox['score'] > 0.6:
            return {
                "sentiment": "Negative",
                "keywords": extract_keywords(original_text)
            }
    except:
        pass

    # 🚨 STEP 2: Sarcasm
    for s in sarcasm_indicators:
        if s in text:
            return {
                "sentiment": "Negative",
                "keywords": extract_keywords(original_text)
            }

    # 🚨 STEP 3: Negation
    for word in positive_words:
        for neg in negation_words:
            if f"{neg} {word}" in text:
                return {
                    "sentiment": "Negative",
                    "keywords": extract_keywords(original_text)
                }

    for word in negative_words:
        for neg in negation_words:
            if f"{neg} {word}" in text:
                return {
                    "sentiment": "Positive",
                    "keywords": extract_keywords(original_text)
                }

    # 🚨 STEP 4: Emoji + keyword scoring
    pos_count = 0
    neg_count = 0

    for pe in positive_emojis:
        if pe in original_text:
            pos_count += 2

    for ne in negative_emojis:
        if ne in original_text:
            neg_count += 2

    words = set(text.split())

    for w in words:
        if w in positive_words:
            pos_count += 1
        elif w in negative_words:
            neg_count += 1

    if pos_count > neg_count:
        return {
            "sentiment": "Positive",
            "keywords": extract_keywords(original_text)
        }
    elif neg_count > pos_count:
        return {
            "sentiment": "Negative",
            "keywords": extract_keywords(original_text)
        }

    # Very short text: TextBlob polarity only (clearer than ML on tiny inputs)
    if len(original_text.split()) <= 3:
        blob_score = TextBlob(text).sentiment.polarity
        if blob_score > 0.05:
            final = "Positive"
        elif blob_score < -0.05:
            final = "Negative"
        else:
            final = "Neutral"
        return {
            "sentiment": final,
            "keywords": extract_keywords(original_text)
        }

    # 🔥 STEP 5: ML model
    try:
        vec = vectorizer.transform([text])
        pred = model.predict(vec)[0]
        ml_result = "Positive" if pred == 4 else "Negative"
    except Exception:
        ml_result = "Neutral"

    # 🧠 STEP 6: TextBlob
    blob_score = TextBlob(text).sentiment.polarity

    if blob_score > 0.05:
        blob_result = "Positive"
    elif blob_score < -0.05:
        blob_result = "Negative"
    else:
        blob_result = "Neutral"

    # ⚖️ STEP 7: Final — agree with ML; else decide from blob thresholds
    if ml_result == blob_result:
        final = ml_result
    elif blob_score > 0.05:
        final = "Positive"
    elif blob_score < -0.05:
        final = "Negative"
    else:
        final = "Neutral"

    return {
        "sentiment": final,
        "keywords": extract_keywords(original_text)
    }


# 🔥 OPTIONAL: TRENDING FUNCTION
def get_trending(all_texts):
    all_keywords = []

    for text in all_texts:
        all_keywords.extend(extract_keywords(text))

    return Counter(all_keywords).most_common(5)
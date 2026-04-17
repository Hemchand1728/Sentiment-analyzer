import pickle
from textblob import TextBlob
from transformers import pipeline

# 🔥 Load ML model
model = pickle.load(open("model.pkl", "rb"))
vectorizer = pickle.load(open("vectorizer.pkl", "rb"))

# 🔥 Load better Toxicity Model
toxicity_model = pipeline(
    "text-classification",
    model="cardiffnlp/twitter-roberta-base-offensive"
)

# 🔥 Keyword lists
positive_words = [
    "love","like","fond","adore","happy","great","awesome","amazing","good",
    "excellent","fantastic","nice","wonderful","best","enjoy","pleased",
    "satisfied","delight","smile","positive","brilliant","super","cool",
    "beautiful","perfect","incredible","fabulous","outstanding","sweet",
    "loved","likes","lovely","joy","cheerful","excited","glad",
    "lit","fire","based","goat","slay","banger","w","pog","dub","epic","goated"
]

negative_words = [
    "hate","despise","worst","bad","angry","terrible","awful","horrible",
    "disgust","annoy","irritate","sad","pain","cry","negative","ugly",
    "stupid","useless","boring","tired","frustrated","depressed","mad",
    "furious","disappointed","sucks","waste","problem","fail","loser",
    "hurt","damn","regret","fear","nasty",
    "cringe","mid","trash","ratio","flop","l","smh","cap","bullshit","garbage","ass","stfu","wtf"
]

# 🔥 Sarcasm indicators
sarcasm_indicators = [
    "🙄", "yeah right", "as if", "wow", "great... not", "not really", "uh huh"
]

# 🔥 Negation words
negation_words = ["not", "no", "never", "n't"]

# 🔥 Emojis
positive_emojis = ["🔥", "💯", "❤️", "😍", "🙌", "👏", "🐐", "✨", "🥰", "💪", "😎", "🤩"]
negative_emojis = ["🤮", "💩", "🗑️", "🤡", "😡", "🤬", "👎", "🤢", "🤦", "🖕", "💔", "🥱"]


def get_sentiment(text):
    original_text = str(text)
    text = original_text.lower()

    # 🚨 STEP 1: Toxicity detection (AI)
    try:
        tox = toxicity_model(original_text)[0]

        if ("OFFENSIVE" in tox['label'] or "LABEL_1" in tox['label']) and tox['score'] > 0.6:
            # Treat toxic/offensive as Negative everywhere in the app.
            return "Negative"
    except:
        pass

    # 🚨 STEP 2: Sarcasm detection
    for s in sarcasm_indicators:
        if s in text:
            return "Negative"

    # 🚨 STEP 3: Negation handling
    for word in positive_words:
        for neg in negation_words:
            if f"{neg} {word}" in text:
                return "Negative"

    for word in negative_words:
        for neg in negation_words:
            if f"{neg} {word}" in text:
                return "Positive"

    # 🚨 STEP 4: Emoji + keyword scoring
    pos_count = 0
    neg_count = 0

    for pe in positive_emojis:
        if pe in original_text:
            pos_count += 2

    for ne in negative_emojis:
        if ne in original_text:
            neg_count += 2

    words = set(text.replace(".", "").replace(",", "").replace("!", "").replace("?", "").split())

    for w in words:
        if w in positive_words:
            pos_count += 1
        elif w in negative_words:
            neg_count += 1

    if pos_count > neg_count:
        return "Positive"
    elif neg_count > pos_count:
        return "Negative"

    # 🚨 STEP 4.5: Unknown insult handling (IMPORTANT FIX)
    blob_score = TextBlob(text).sentiment.polarity
    if pos_count == 0 and neg_count == 0:
        if blob_score < -0.05:
            return "Negative"

    # 🔥 STEP 5: ML model
    try:
        vec = vectorizer.transform([text])
        pred = model.predict(vec)[0]
        ml_result = "Positive" if pred == 4 else "Negative"
    except:
        ml_result = "Neutral"

    # 🧠 STEP 6: TextBlob fallback
    if blob_score > 0.2:
        blob_result = "Positive"
    elif blob_score < -0.2:
        blob_result = "Negative"
    else:
        blob_result = "Neutral"

    # ⚖️ STEP 7: Final decision (SMART)
    if ml_result == blob_result:
        return ml_result

    if blob_score < -0.3:
        return "Negative"
    elif blob_score > 0.3:
        return "Positive"
    else:
        return "Neutral"
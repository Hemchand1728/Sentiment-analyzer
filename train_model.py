import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.linear_model import LogisticRegression
import pickle

# Load dataset
df = pd.read_csv('data/training.1600000.processed.noemoticon.csv', encoding='latin-1', header=None)

# Rename columns
df.columns = ['target', 'id', 'date', 'flag', 'user', 'text']

# Use only required columns
df = df[['target', 'text']]

# Use small sample (SAFE for your Mac)
df = df.sample(20000)

# Convert labels (4 → 1, 0 → 0)
df['target'] = df['target'].apply(lambda x: 1 if x == 4 else 0)

# Split data
X_train, X_test, y_train, y_test = train_test_split(df['text'], df['target'], test_size=0.2)

# Convert text to numbers
vectorizer = CountVectorizer(stop_words='english')
X_train_vec = vectorizer.fit_transform(X_train)
X_test_vec = vectorizer.transform(X_test)

# Train model
model = LogisticRegression(max_iter=200)
model.fit(X_train_vec, y_train)

# Accuracy
accuracy = model.score(X_test_vec, y_test)
print("Accuracy:", accuracy)

# Save model
pickle.dump(model, open('model.pkl', 'wb'))
pickle.dump(vectorizer, open('vectorizer.pkl', 'wb'))

print("Model saved successfully!")
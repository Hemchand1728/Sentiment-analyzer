import pandas as pd
from models.preprocess import clean_text
from models.sentiment import get_sentiment

df = pd.read_csv('data/testdata.manual.2009.06.14.csv', encoding='latin-1', header=None)

df.columns = ['target', 'id', 'date', 'flag', 'user', 'text']

df = df[['target', 'text']]

df['sentiment'] = df['target'].apply(lambda x: 'Positive' if x == 4 else 'Negative')

df['clean_text'] = df['text'].apply(clean_text)

df['predicted'] = df['clean_text'].apply(get_sentiment)

print(df[['clean_text', 'sentiment', 'predicted']].head())
df['predicted'] = df['clean_text'].apply(get_sentiment)

print(df[['clean_text', 'sentiment', 'predicted']].head())
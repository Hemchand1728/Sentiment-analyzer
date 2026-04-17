import re

def clean_text(text):
    text = str(text).lower()
    text = re.sub(r"http\S+", "", text)   # remove links
    text = re.sub(r"@\w+", "", text)      # remove mentions
    text = re.sub(r"#", "", text)         # remove hashtags
    text = re.sub(r"[^a-zA-Z\s]", "", text)  # remove symbols
    return text


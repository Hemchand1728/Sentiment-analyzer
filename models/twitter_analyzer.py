from __future__ import annotations

import json
import logging
import os
import re
import urllib.parse
import urllib.request
from collections import Counter
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from models.sentiment import get_sentiment

logger = logging.getLogger(__name__)


def _sentiment_label(value: Any) -> str:
    """
    models/sentiment.get_sentiment() currently returns either:
    - a string label (older behavior), OR
    - a dict like {"sentiment": "Positive", "keywords": [...]} (newer behavior)
    This helper keeps Twitter analyzer compatible without touching existing routes.
    """
    if isinstance(value, dict):
        label = value.get("sentiment")
        return str(label) if label else "Neutral"
    if isinstance(value, str):
        return value
    return "Neutral"


_WORD_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9_']{1,}")
_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "if", "then", "else", "when", "while",
    "is", "are", "was", "were", "be", "been", "being",
    "to", "of", "in", "on", "for", "with", "at", "by", "from", "as", "about",
    "it", "its", "this", "that", "these", "those",
    "i", "me", "my", "we", "our", "you", "your", "he", "she", "they", "them",
    "rt", "https", "http", "com", "co", "t", "amp",
}


def _simple_trending(texts: List[str], *, keyword: str, limit: int = 5) -> List[List[Any]]:
    kw = (keyword or "").strip().lower()
    counts: Counter[str] = Counter()
    for txt in texts:
        for w in _WORD_RE.findall((txt or "").lower()):
            if w in _STOPWORDS:
                continue
            if kw and w == kw:
                continue
            if w.startswith("#"):
                w = w[1:]
            if len(w) < 3:
                continue
            counts[w] += 1
    return [[w, int(c)] for w, c in counts.most_common(limit)]


def _fetch_via_http(bearer_token: str, query: str, *, max_results: int) -> List[str]:
    """Twitter API v2 recent search — returns tweet texts only; no synthetic data."""
    params = {
        "query": query,
        "max_results": str(max(10, min(int(max_results), 100))),
    }
    url = "https://api.twitter.com/2/tweets/search/recent?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {bearer_token}",
            "User-Agent": "sentiment-analyzer/1.0",
        },
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=12) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    payload = json.loads(raw)
    data = payload.get("data") or []
    out: List[str] = []
    for item in data:
        if isinstance(item, dict) and item.get("text"):
            out.append(str(item["text"]))
    return out


@dataclass(frozen=True)
class TwitterAnalyzer:
    """
    Fetches tweets via Twitter API v2 (Tweepy preferred, HTTP fallback).
    Never returns placeholder or repeated sample tweets.
    """

    bearer_token: Optional[str] = None

    def fetch_tweets(self, keyword: str, *, count: int = 10) -> List[str]:
        keyword = (keyword or "").strip()
        if not keyword:
            return []

        token = (self.bearer_token or os.environ.get("TWITTER_BEARER_TOKEN") or "").strip()
        if not token:
            logger.warning("TWITTER_BEARER_TOKEN not set; cannot fetch tweets.")
            return []

        query = f"{keyword} -is:retweet lang:en"
        max_results = max(10, min(int(count), 100))

        # Prefer Tweepy (matches documented Client.search_recent_tweets usage)
        try:
            import tweepy

            client = tweepy.Client(bearer_token=token, wait_on_rate_limit=False)
            response = client.search_recent_tweets(
                query=query,
                max_results=max_results,
            )
            if not response or not getattr(response, "data", None):
                return []
            texts: List[str] = []
            for tweet in response.data:
                t = getattr(tweet, "text", None)
                if t:
                    texts.append(str(t))
            return texts[:count] if texts else []
        except ImportError:
            logger.info("tweepy not installed; using HTTP client for Twitter API v2.")
        except Exception as e:
            logger.warning("Tweepy search failed (%s); trying HTTP fallback.", e)

        try:
            texts = _fetch_via_http(token, query, max_results=max_results)
            return texts[:count] if texts else []
        except Exception as e:
            logger.warning("Twitter HTTP fetch failed: %s", e)
            return []

    def analyze_keyword(self, keyword: str, *, count: int = 10) -> Dict[str, Any]:
        tweets = self.fetch_tweets(keyword, count=count)
        results: List[Dict[str, str]] = []

        summary = {"positive": 0, "negative": 0, "neutral": 0}
        for t in tweets:
            label = _sentiment_label(get_sentiment(t))
            norm = label.capitalize() if isinstance(label, str) else "Neutral"
            if norm not in ("Positive", "Negative", "Neutral"):
                norm = "Neutral"

            if norm == "Positive":
                summary["positive"] += 1
            elif norm == "Negative":
                summary["negative"] += 1
            else:
                summary["neutral"] += 1

            results.append({"tweet": t, "sentiment": norm})

        trending = _simple_trending(tweets, keyword=keyword, limit=5) if tweets else []
        return {"tweets": results, "summary": summary, "trending": trending}

# Sentiment Analyzer

A full-stack Sentiment Analysis web application built using Flask, MongoDB, and Natural Language Processing (NLP) techniques. The application analyzes user-entered text and classifies sentiment as **Positive**, **Negative**, or **Neutral**, while also extracting keywords, tracking trends, and providing admin analytics.

## Project Overview

This project was developed to create an interactive platform where users can:
- Register and log in securely
- Analyze sentiment from text input
- View sentiment history
- Explore keyword trends and analytics
- Access an admin dashboard for monitoring usage and insights

The project combines **backend development**, **database integration**, **frontend design**, and **AI/NLP-based text processing** into one complete application.

## Features

- User Authentication (Login / Register / Logout)
- Session-based protected routes
- Text sentiment classification (Positive / Negative / Neutral)
- Keyword extraction using NLP
- Trend and search-history analytics
- Admin login and dashboard
- Responsive frontend UI
- MongoDB cloud database integration
- Fallback tweet generation system for analysis without external API dependency

## Tech Stack

### Frontend
- HTML
- CSS
- JavaScript

### Backend
- Python
- Flask

### Database
- MongoDB Atlas

### NLP / AI
- TextBlob (sentiment polarity scoring)
- spaCy (keyword extraction)
- Rule-based sentiment enhancements (keywords + emojis)

## How Sentiment Analysis Works

1. User enters text.
2. The text is cleaned and preprocessed.
3. TextBlob calculates polarity.
4. Rule-based logic improves accuracy using positive/negative keywords and emojis.
5. spaCy extracts meaningful keywords.
6. Final sentiment is classified as Positive, Negative, or Neutral.

## Twitter Analysis Limitation

Initially, the project was designed to fetch live tweets using the Twitter/X API for real-time sentiment analysis.

However:
- Twitter API access is paid
- Free access is highly restricted
- Rate limits reduce usability for student/demo projects
- Continuous API dependency reduces reliability

Because of these cost and access constraints, relying on the Twitter API was not practical for this project.

## Fallback Data Generation System

To solve the API limitation, a **Fallback Data Generation System** was implemented.

Instead of fetching paid API data, the system generates realistic tweet-like content dynamically.

### How fallback works

1. User enters a keyword (example: AI, Cricket, iPhone).
2. The keyword is categorized into a topic domain.
3. Predefined templates are selected such as:
   - Opinions
   - Questions
   - Reactions
   - Experiences
4. The keyword is injected into those templates.
5. Emojis, punctuation, and random variations are added.
6. Duplicate content is filtered.
7. Generated content is analyzed just like real tweets.

### Example

Keyword: `AI`

Generated fallback tweets:
- "AI is changing everything 🔥"
- "What do you think about AI?"
- "Honestly, AI looks very promising 😊"
- "Not sure if AI will replace jobs 😟"

This ensures the project remains functional, realistic, and reliable even without external API access.

## Database Collections

- `users` – stores user accounts
- `history` – stores sentiment analysis history
- `search_history` – stores keyword searches
- `feedback` – stores user feedback

## Project Outcome

This project demonstrates:
- Full-stack web development
- Database design
- Authentication systems
- NLP implementation
- Analytics dashboards
- Problem-solving through fallback system design
- Building reliable systems without paid external dependencies

## Future Improvements

- Integrate live APIs when affordable access is available
- Add multilingual sentiment analysis
- Improve dashboard analytics
- Add ML model fine-tuning for higher accuracy
- Deploy production-scale version

## Author

**Hemachandu Gunthati**




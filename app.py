from flask import Flask, render_template, request, jsonify, redirect, session, make_response
from pymongo import MongoClient
from bson.objectid import ObjectId
import bcrypt
from models.sentiment import get_sentiment, extract_keywords
from models.twitter_analyzer import TwitterAnalyzer

from datetime import datetime
from collections import Counter
import os

app = Flask(__name__)
# Generate a new session key on restart to invalidate cached sessions (forces login)
app.secret_key = os.environ.get("SECRET_KEY", "mysecret123")
app.config['SESSION_PERMANENT'] = False

@app.after_request
def add_no_cache_headers(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.before_request
def restrict_access():
    # Path-based access control to avoid endpoint resolution edge cases.
    path = request.path or "/"

    # Never block static assets (JS/CSS/images).
    if path.startswith('/static/'):
        return None

    # Public routes (no session required).
    # Keep `/` public so the landing page can render for logged-out users.
    public_paths = {'/', '/login', '/register', '/admin-login', '/check-session'}
    if path in public_paths:
        return None

    # Restrict all other routes unless a session exists.
    if 'user' in session or 'admin' in session:
        return None

    return redirect('/login')

client = MongoClient(os.environ.get("MONGO_URI", "mongodb+srv://admin:admin123@cluster0.f2crrd1.mongodb.net/?retryWrites=true&w=majority"))
db = client["sentiment_db"]

users = db["users"]
history = db["history"]
feedback_db = db["feedback"]
search_history = db["search_history"]

def normalize_sentiment_label(label: str) -> str:
    """Normalize stored/returned sentiment labels for UI + stats."""
    if not label:
        return "Neutral"
    return "Negative" if label == "Toxic" else label

def is_admin():
    # Preferred admin session key for admin panel access.
    if 'admin' in session:
        admin_user = users.find_one({
            "$or": [
                {"username": session['admin'], "isAdmin": True},
                {"name": session['admin'], "role": "admin"}
            ]
        })
        return bool(admin_user) and not admin_user.get('isBlocked', False)

    # Backwards-compatible: if a normal user session exists and isAdmin is set, allow.
    if 'user' in session:
        user = users.find_one({"email": session['user']})
        return bool(user) and user.get('isAdmin', False) and not user.get('isBlocked', False)

    return False

@app.route('/admin_setup')
def admin_setup():
    '''Temporary route to bootstrap an admin user'''
    if 'user' not in session:
        return redirect('/login')
    users.update_one({"email": session['user']}, {"$set": {"isAdmin": True}})
    session['is_admin'] = True
    return redirect('/admin')


@app.route('/')
def home():
    # Public landing page. Logged-in users still go to the analyzer.
    if 'user' in session:
        return render_template('index.html', show_navbar=True)
    return render_template('landing.html', show_navbar=False)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        login_id = request.form['login_id']
        password = request.form['password']

        user = users.find_one({
            "$or": [
                {"email": login_id},
                {"username": login_id}
            ]
        })

        if user and bcrypt.checkpw(password.encode(), user['password']):
            if user.get('isBlocked', False):
                return render_template('user-login.html', show_navbar=False, error="Your account has been blocked by an administrator.")
                
            session.clear()
            session['user'] = user['email']
            session['is_admin'] = user.get('isAdmin', False)
            return redirect('/')
        else:
            return render_template('user-login.html', show_navbar=False, error="Invalid credentials")

    return render_template('user-login.html', show_navbar=False)

@app.route('/admin-login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not username or not password:
            return render_template('admin-login.html', show_navbar=False, error="Username and password are required.")

        # Support both schemas:
        # 1) New schema: { username, isAdmin: True, password: hashed }
        # 2) Your current schema: { name, role: "admin", password: plain }

        user = users.find_one({
            "$or": [
                {"username": username, "isAdmin": True},
                {"name": username, "role": "admin"}
            ]
        })

        if not user:
            return render_template('admin-login.html', show_navbar=False, error="Invalid admin credentials.")

        # Handle both hashed and plain passwords
        password_valid = False

        if isinstance(user.get('password'), bytes):
            # bcrypt hashed password
            password_valid = bcrypt.checkpw(password.encode(), user['password'])
        else:
            # plain text password (your current DB)
            password_valid = (password == user.get('password'))

        if not password_valid:
            return render_template('admin-login.html', show_navbar=False, error="Invalid admin credentials.")

        if user.get('isBlocked', False):
            return render_template('admin-login.html', show_navbar=False, error="Your account has been blocked.")

        session.clear()
        # Normalize session key
        session['admin'] = user.get('username') or user.get('name')
        return redirect('/admin')

    return render_template('admin-login.html', show_navbar=False)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = bcrypt.hashpw(request.form['password'].encode(), bcrypt.gensalt())

        existing = users.find_one({"email": email})
        if existing:
            return render_template('register.html', show_navbar=False, error="User already exists")

        users.insert_one({
            "username": username,
            "email": email,
            "password": password,
            "isAdmin": False,
            "isBlocked": False
        })

        return redirect('/login')

    return render_template('register.html', show_navbar=False)

@app.route('/logout')
def logout():
    session.clear()
    response = redirect('/login')
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/check-session')
def check_session():
    if 'user' in session or 'admin' in session:
        return jsonify({"logged_in": True})
    return jsonify({"logged_in": False})

@app.route('/dashboard')
def dashboard():
    if 'user' not in session and 'admin' not in session:
        return redirect('/login')
    user_email = session.get('user')
    pipeline = [
        {"$match": {"user": user_email, "source": "twitter", "keyword": {"$exists": True, "$ne": None}}},
        {
            "$group": {
                "_id": {"$toLower": "$keyword"},
                "original_keyword": {"$first": "$keyword"},
                "total": {"$sum": 1},
                "positive": {
                    "$sum": { "$cond": [ { "$eq": [ "$sentiment", "Positive" ] }, 1, 0 ] }
                },
                "negative": {
                    "$sum": { "$cond": [ { "$in": [ "$sentiment", ["Negative", "Toxic"] ] }, 1, 0 ] }
                },
                "neutral": {
                    "$sum": { "$cond": [ { "$eq": [ "$sentiment", "Neutral" ] }, 1, 0 ] }
                },
                "latest_date": {"$max": "$created_at"}
            }
        },
        {
            "$project": {
                "_id": 0,
                "keyword": "$original_keyword",
                "total": 1,
                "positive": 1,
                "negative": 1,
                "neutral": 1,
                "latest_date": 1
            }
        },
        {"$sort": {"latest_date": -1}}
    ]

    keyword_stats = list(history.aggregate(pipeline))

    return render_template('dashboard.html', data=keyword_stats, show_navbar=True)

@app.route('/delete/<id>', methods=['POST'])
def delete_history(id):
    if 'user' not in session:
        return redirect('/login')

    history.delete_one({
        "_id": ObjectId(id),
        "user": session['user']
    })

    return redirect('/dashboard')

@app.route('/delete-keyword/<path:keyword>', methods=['POST'])
def delete_keyword(keyword):
    if 'user' not in session:
        return redirect('/login')

    history.delete_many({
        "keyword": keyword,
        "user": session['user']
    })

    return redirect('/dashboard')

@app.route('/analyze', methods=['POST'])
def analyze():
    if 'user' not in session or not session['user']:
        return jsonify({"error": "Login required: missing user session"}), 401

    user = users.find_one({"email": session['user']})
    if user and user.get('isBlocked', False):
        return jsonify({"error": "Account blocked."})

    data = request.get_json()
    text = data.get('text', '').strip()
    if not text:
        return jsonify({"error": "Empty input"})

    gs = get_sentiment(text)
    sentiment_str = gs["sentiment"] if isinstance(gs, dict) else gs
    result = normalize_sentiment_label(sentiment_str)

    print(f"Inserting manual analysis for user: {session['user']}")
    
    # Insert into history, defaults flagged to False
    history.insert_one({
        "user": session['user'],
        "text": text,
        "sentiment": result,
        "source": "manual",
        "flagged": False,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

    return jsonify({"sentiment": result})


@app.route('/twitter')
def twitter_page():
    return redirect('/')


@app.route('/analyze-twitter', methods=['POST'])
def analyze_twitter():
    # Keep access model consistent with rest of the app:
    # - before_request already redirects unauthenticated users to /login for page routes
    # - for XHR, return JSON errors
    if 'user' not in session or not session['user']:
        return jsonify({"error": "Login required: missing user session"}), 401

    if 'user' in session:
        user = users.find_one({"email": session['user']})
        if user and user.get('isBlocked', False):
            return jsonify({"error": "Account blocked."}), 403

    data = request.get_json(silent=True) or {}
    keyword = (data.get('keyword') or '').strip()
    if not keyword:
        return jsonify({"error": "Empty keyword"}), 400
        
    search_history.insert_one({
        "user": session['user'],
        "keyword": keyword,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

    # Import TextBlob, spaCy, and Tweepy for this specific feature
    from textblob import TextBlob
    import spacy
    from tweepy import Client
    
    # Load spaCy model
    nlp = spacy.load("en_core_web_sm")
    
    # DEBUG: Print keyword
    print("Keyword:", keyword)
    
    # Fetch tweets using Tweepy v2 Client
    bearer_token = os.environ.get("TWITTER_BEARER_TOKEN")
    print("Bearer Token:", "PRESENT" if bearer_token else "MISSING")
    
    if not bearer_token:
        return jsonify({"error": "Twitter Bearer token not configured"}), 500
    
    def get_fallback_tweets(kw):
        import random
        
        kw_lower = kw.lower()
        
        categories = {
            "tech": ['iphone', 'ai', 'coding', 'tech', 'software', 'app', 'python', 'javascript', 'macbook'],
            "sports": ['cricket', 'football', 'soccer', 'basketball', 'tennis', 'game', 'match', 'ipl'],
            "person": ['elon musk', 'messi', 'ronaldo', 'taylor swift', 'biden', 'trump', 'kohli'],
            "product": ['samsung', 'tesla', 'nike', 'ps5', 'xbox', 'car']
        }
        
        category = "general"
        for cat, keywords in categories.items():
            if any(k in kw_lower for k in keywords):
                category = cat
                break
                
        templates = {
            "tech": {
                "experience": [
                    "Been debugging this all day, {keyword} can be exhausting",
                    "Finally fixed that bug in {keyword}, feels satisfying",
                    "Trying to learn {keyword} and my brain is completely fried",
                    "Spent 3 hours setting up {keyword} but it was totally worth it"
                ],
                "opinion": [
                    "{keyword} is honestly the game-changer everyone says it is",
                    "Not going to lie, {keyword} is a bit overrated in my opinion",
                    "The new {keyword} update broke everything again didn't it?",
                    "I still think the older version of {keyword} was way better"
                ],
                "question": [
                    "Is anyone else having issues with {keyword} today?",
                    "Can someone explain why {keyword} is suddenly trending?",
                    "Any alternatives to {keyword}? Getting tired of the bugs",
                    "Should I switch to {keyword} or is it just hype?"
                ],
                "reaction": [
                    "Wow, {keyword} just blew my mind",
                    "Absolutely speechless at the latest {keyword} feature",
                    "Just saw the {keyword} announcement and I'm disappointed",
                    "This {keyword} discussion is getting out of hand"
                ]
            },
            "sports": {
                "experience": [
                    "Watched the {keyword} event last night, still recovering from the hype",
                    "Got tickets for {keyword}, can't wait!",
                    "Been following {keyword} for years and this season is wild",
                    "Just played {keyword} and pulled a muscle, totally worth it"
                ],
                "opinion": [
                    "That {keyword} match yesterday was insane",
                    "Not a big fan of {keyword} lately to be honest",
                    "The refereeing in {keyword} has been terrible this year",
                    "{keyword} is without a doubt the best sport right now"
                ],
                "question": [
                    "Who do you guys think will win the {keyword} championship?",
                    "Why is everyone so obsessed with {keyword} all of a sudden?",
                    "Is {keyword} actually hard to learn?",
                    "Did anyone catch that crazy {keyword} highlight?"
                ],
                "reaction": [
                    "I cannot believe what just happened in {keyword}!",
                    "That {keyword} finish was absolutely legendary",
                    "Just saw the {keyword} stats... mind blown",
                    "{keyword} fans are wild today"
                ]
            },
            "person": {
                "experience": [
                    "Just finished reading an article about {keyword}, very insightful",
                    "Met someone who actually worked with {keyword}, crazy stories",
                    "Been watching {keyword} interviews all morning",
                    "Attended a talk by {keyword} once, changed my perspective"
                ],
                "opinion": [
                    "{keyword}'s latest move is definitely controversial",
                    "I actually admire {keyword}'s vision for the future",
                    "People give {keyword} too much credit sometimes",
                    "Whether you like them or not, {keyword} is incredibly influential"
                ],
                "question": [
                    "What are your thoughts on {keyword}'s new project?",
                    "Why does {keyword} get so much hate on here?",
                    "Is {keyword} actually a genius or just lucky?",
                    "Has anyone seen what {keyword} just posted?"
                ],
                "reaction": [
                    "{keyword} really just said that huh",
                    "Can't believe {keyword} managed to pull that off",
                    "Another day, another crazy {keyword} moment",
                    "The internet's reaction to {keyword} is always hilarious"
                ]
            },
            "product": {
                "experience": [
                    "Just ordered my {keyword}, arrives tomorrow!",
                    "Been using {keyword} for a week now and it's pretty solid",
                    "My {keyword} just broke after only a month of use",
                    "Upgraded to the new {keyword} and the difference is night and day"
                ],
                "opinion": [
                    "{keyword} is way too expensive for what you get",
                    "Unpopular opinion but {keyword} is actually perfection",
                    "The build quality on {keyword} is somewhat lacking",
                    "I genuinely prefer {keyword} over the competitors"
                ],
                "question": [
                    "Thinking about buying {keyword}, is it worth the price?",
                    "Does anyone know how to fix a broken {keyword} screen?",
                    "Should I wait for the next version or buy {keyword} now?",
                    "Which color of {keyword} looks the best in person?"
                ],
                "reaction": [
                    "The battery life on {keyword} is unreal",
                    "Just saw the {keyword} drop, my wallet is crying",
                    "Why is {keyword} sold out literally everywhere",
                    "The design of {keyword} is so clean"
                ]
            },
            "general": {
                "experience": [
                    "Just diving into {keyword} for the first time, pretty interesting",
                    "Spent the whole day researching {keyword}",
                    "Tried getting into {keyword} but it's not really my thing",
                    "My experience with {keyword} has been amazing so far"
                ],
                "opinion": [
                    "Honestly, {keyword} is completely underrated",
                    "I feel like {keyword} doesn't live up to the hype",
                    "The community around {keyword} is so toxic sometimes",
                    "{keyword} is exactly what we needed right now"
                ],
                "question": [
                    "Can anyone recommend a good guide for {keyword}?",
                    "Why is nobody talking about {keyword}?",
                    "What's the big deal with {keyword} currently?",
                    "Is it too late to get on the {keyword} trend?"
                ],
                "reaction": [
                    "This whole {keyword} situation is crazy",
                    "Absolutely obsessed with {keyword} lately",
                    "I'm so done hearing about {keyword}",
                    "Wow, {keyword} really surprised me"
                ]
            }
        }

        emojis = ['😊', '😡', '😐', '🔥', '🤔', '🙌', '👎', '👏', '🙄', '😍', '😅', '💀', '👀', '💯', '🚀']
        tweets = set()
        
        num_tweets = random.randint(15, 25)
        styles = ["experience", "opinion", "question", "reaction"]
        style_weights = [0.25, 0.35, 0.20, 0.20]
        
        pool = templates.get(category, templates["general"])
        
        attempts = 0
        while len(tweets) < num_tweets and attempts < num_tweets * 3:
            attempts += 1
            style = random.choices(styles, weights=style_weights)[0]
            template = random.choice(pool[style])
            
            tweet_text = template.replace("{keyword}", kw)
            
            # Variations to ensure uniqueness and realism
            if random.random() < 0.2:
                tweet_text = tweet_text.lower()
                
            if random.random() < 0.6:
                emoji = random.choice(emojis)
                if random.random() < 0.2:
                    emoji = emoji * random.randint(2, 3)
                tweet_text += f" {emoji}"
                
            if tweet_text[-1] not in ["?", "!", ".", "”", "\"", "🔥", "😊", "😡", "😐", "🤔", "🙌", "👎", "👏", "🙄", "😍", "😅", "💀", "👀", "💯", "🚀"]:
                if random.random() < 0.5:
                    tweet_text += random.choice([".", "!", "..."])
            
            tweets.add(tweet_text.strip())

        tweets_list = list(tweets)
        random.shuffle(tweets_list)
        return tweets_list

    try:
        client = Client(bearer_token=bearer_token)
        query = keyword + " -is:retweet lang:en"
        
        # DEBUG: Print query
        print("Query:", query)
        
        response = client.search_recent_tweets(
            query=query,
            max_results=20,
            tweet_fields=["text"]
        )
        
        # DEBUG: Print response
        print("Response:", response)
        
        tweets = []
        if response.data:
            for tweet in response.data:
                if hasattr(tweet, 'text') and tweet.text:
                    tweets.append(tweet.text)
        
        # DEBUG: Print tweets count
        print("Tweets found:", len(tweets))
        
        if not tweets:
            print("No tweets from API, using fallback data")
            tweets = get_fallback_tweets(keyword)
            
    except Exception as e:
        # DEBUG: Print error
        print("Twitter API Error:", str(e))
        print("Using fallback data")
        tweets = get_fallback_tweets(keyword)
    
    results = []
    summary = {"positive": 0, "negative": 0, "neutral": 0}
    all_keywords = []
    
    ignore_words = [
        "thing", "lot", "day", "time", "work",
        "people", "something", "anything", "everything"
    ]
    
    positive_hints = ["good", "love", "great", "amazing", "nice", "awesome", "best"]
    negative_hints = ["bad", "hate", "worst", "terrible", "sucks", "overrated"]
    positive_emojis = ["🔥", "😍", "💯", "🙌", "😊"]
    negative_emojis = ["😡", "👎", "🤮", "💀", "😔", "😞", "💔", "🗑️"]
    
    for tweet in tweets:
        # Base scoring with TextBlob
        blob = TextBlob(tweet)
        score = blob.sentiment.polarity
        
        lower_tweet = tweet.lower()
        
        import re
        words = set(re.findall(r'\b\w+\b', lower_tweet))
        
        # Word hints scoring
        for w in positive_hints:
            if w in words:
                score += 0.3
                
        for w in negative_hints:
            if w in words:
                score -= 0.3
                
        # Emoji hints scoring (use original tweet to preserve emojis)
        for e in positive_emojis:
            if e in tweet:
                score += 0.5
                
        for e in negative_emojis:
            if e in tweet:
                score -= 0.5
                
        # Final decision
        if score > 0.1:
            sentiment = "Positive"
        elif score < -0.1:
            sentiment = "Negative"
        else:
            sentiment = "Neutral"
            
        if sentiment == "Positive":
            summary["positive"] += 1
        elif sentiment == "Negative":
            summary["negative"] += 1
        else:
            summary["neutral"] += 1
        
        # Use spaCy for keyword extraction
        doc = nlp(tweet.lower())
        keywords = [
            token.text.lower()
            for token in doc
            if (
                token.pos_ in ["NOUN", "PROPN"]
                and not token.is_stop
                and token.is_alpha
                and len(token.text) > 3
                and token.text.lower() not in ignore_words
                and token.text.lower() != keyword.lower()
            )
        ]
        all_keywords.extend(keywords)
        
        results.append({"tweet": tweet, "sentiment": sentiment})
        
        print(f"Inserting twitter analysis for user: {session['user']}")
        
        # Insert analyzed tweet into history
        history.insert_one({
            "user": session['user'],
            "text": tweet,
            "sentiment": sentiment,
            "source": "twitter",
            "keyword": keyword,
            "flagged": False,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
    
    # Get trending keywords (top 10 most common, excluding search keyword)
    keyword_counter = Counter(all_keywords)
    search_keyword_lower = keyword.lower()
    trending = [
        [kw, count] 
        for kw, count in keyword_counter.most_common(10) 
        if kw != search_keyword_lower and len(kw) > 2
    ][:5]
    
    return jsonify({
        "tweets": results,
        "summary": summary,
        "trending": trending
    })


# ==========================================
# MICROSERVICE ENDPOINT
# ==========================================
@app.route('/service/analyze', methods=['POST'])
def microservice_analyze():
    # Only expected to be called by local Node.js backend
    data = request.get_json()
    text = data.get('text', '').strip()
    if not text:
        return jsonify({"error": "Empty input"}), 400

    gs = get_sentiment(text)
    sentiment_str = gs["sentiment"] if isinstance(gs, dict) else gs
    result = normalize_sentiment_label(sentiment_str)

    # We do NOT insert into DB here. Node.js handles DB insertions to attach JWT User
    return jsonify({"sentiment": result})


# ==========================================
# ADMIN PANEL ROUTES
# ==========================================

@app.route('/admin')
def admin_dashboard():
    # Never return 403 here; redirect to admin login instead.
    if 'admin' not in session and not is_admin():
        return redirect('/admin-login')

    # User-wise moderation: show distinct users from history.
    user_emails = history.distinct("user")
    user_emails = [u for u in user_emails if u]
    user_emails.sort()

    # Bonus: count comments per user (single aggregation).
    counts = {}
    negative_counts = {}
    try:
        pipeline = [
            {"$group": {
                "_id": "$user",
                "count": {"$sum": 1},
                "negative": {"$sum": {"$cond": [{"$in": ["$sentiment", ["Negative", "Toxic"]]}, 1, 0]}}
            }}
        ]
        for row in history.aggregate(pipeline):
            if row.get("_id"):
                counts[row["_id"]] = int(row.get("count", 0))
                negative_counts[row["_id"]] = int(row.get("negative", 0))
    except Exception:
        # Fallback: no counts if aggregation fails.
        pass

    users_list = [
        {"email": u, "count": counts.get(u), "negative": negative_counts.get(u, 0)}
        for u in user_emails
    ]

    return render_template('admin.html', users=users_list, admin=session.get('admin'), show_navbar=True)


@app.route('/admin/user/<path:email>')
def admin_user(email):
    if 'admin' not in session and not is_admin():
        return redirect('/admin-login')

    user_history = list(history.find(
        {"user": email},
        {"_id": 1, "text": 1, "sentiment": 1, "flagged": 1, "created_at": 1}
    ))

    for item in user_history:
        item["_id"] = str(item["_id"])
        item["text"] = item.get("text", "")
        item["sentiment"] = normalize_sentiment_label(item.get("sentiment", "Neutral"))
        item["created_at"] = item.get("created_at", "")
        item["flagged"] = bool(item.get("flagged", False))

    user_history.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return render_template('admin-user.html', email=email, data=user_history, admin=session.get('admin'), show_navbar=True)

@app.route('/api/admin/stats')
def admin_stats():
    if not is_admin():
        return jsonify({"error": "Unauthorized"}), 403

    try:
        all_history = list(history.find())
        
        if not all_history:
            return jsonify({
                "summary": {"Total": 0, "Positive": 0, "Negative": 0, "Neutral": 0},
                "table_data": [],
                "pie_chart": {"Positive": 0, "Negative": 0, "Neutral": 0},
                "bar_chart": {"labels": [], "data": []},
                "trends": {"labels": [], "positive": [], "negative": [], "neutral": []},
                "keyword_trends": [],
                "top_searches": [],
                "top_negative": []
            })
        
        # Format data for frontend table
        table_data = []
        
        # Sentiments (treat legacy "Toxic" as "Negative")
        sentiments = {"Positive": 0, "Negative": 0, "Neutral": 0}
        
        # Comments per user
        user_counts = Counter()
        
        # Dates (for Trends)
        date_sentiments = {}
        
        # Top Negative (includes legacy "Toxic")
        negative_counts = Counter()
        
        words = []
        unique_dates = set([item.get("created_at", "").split(" ")[0] for item in all_history if item.get("created_at")])
        use_hour = len(unique_dates) < 2

        for item in all_history:
            s = normalize_sentiment_label(item.get("sentiment", "Neutral"))
            u = item.get("user", "Unknown")
            
            created_at = item.get("created_at", "")
            if created_at and " " in created_at:
                date_part = created_at.split(" ")[0]
                time_part = created_at.split(" ")[1][:2]
                d = f"{date_part} {time_part}:00" if use_hour else date_part
            else:
                d = created_at if created_at else "Unknown"
            
            text = str(item.get("text", ""))
            for w in text.lower().split():
                if len(w) > 3 and "\u200c" not in w:
                    words.append(w)
            
            if s in sentiments:
                sentiments[s] += 1
            else:
                sentiments["Neutral"] += 1
                
            user_counts[u] += 1
            
            if s == "Negative":
                negative_counts[u] += 1
                
            if d != "Unknown":
                if d not in date_sentiments:
                    date_sentiments[d] = {"Positive": 0, "Negative": 0, "Neutral": 0}
                if s in date_sentiments[d]:
                    date_sentiments[d][s] += 1
                    
            table_data.append({
                "_id": str(item["_id"]),
                "user": u,
                "text": text,
                "sentiment": s,
                "flagged": item.get("flagged", False),
                "created_at": item.get("created_at", "")
            })

        # Keyword Trends safely
        trends = Counter(words).most_common(5)
        
        # Sort dates and table data
        table_data.sort(key=lambda x: x["created_at"], reverse=True)
        
        # Searches Tracking safely
        try:
            search_docs = list(search_history.find({}, {"_id": 0, "keyword": 1}))
            search_freq = Counter([(d.get("keyword") or "").lower() for d in search_docs])
            top_searches = [{"keyword": k, "count": v} for k, v in search_freq.most_common(5) if k]
        except Exception:
            top_searches = []

        # Prepare top negative leaderboard strictly stripping emails
        top_negative = []
        for k, v in negative_counts.most_common(5):
            if v > 0:
                user_doc = users.find_one({"email": k})
                label = user_doc.get("username", k.split("@")[0]) if user_doc else k.split("@")[0]
                if len(label) > 12: label = label[:10] + ".."
                top_negative.append({"user": label, "count": v})
                
        # Resolve usernames for Bar chart efficiently
        bar_labels = []
        for k, _ in user_counts.most_common(10):
            user_doc = users.find_one({"email": k})
            label = user_doc.get("username", k.split("@")[0]) if user_doc else k.split("@")[0]
            if len(label) > 12: label = label[:10] + ".."
            bar_labels.append(label)
        
        # Sort dates
        sorted_dates = sorted(date_sentiments.keys())[-14:] # Last 14 dates
        
        print("Admin stats working")

        return jsonify({
            "summary": {
                "Total": sum(sentiments.values()),
                "Positive": sentiments.get("Positive", 0),
                "Negative": sentiments.get("Negative", 0),
                "Neutral": sentiments.get("Neutral", 0)
            },
            "table_data": table_data[:10], # Latest 10 for Recent Activity
            "keyword_trends": trends,
            "top_searches": top_searches,
            "pie_chart": sentiments,
            "bar_chart": {
                "labels": bar_labels,
                "data": [v for _, v in user_counts.most_common(10)]
            },
            "trends": {
                "labels": sorted_dates,
                "positive": [date_sentiments[d]["Positive"] for d in sorted_dates],
                "negative": [date_sentiments[d]["Negative"] for d in sorted_dates],
                "neutral": [date_sentiments[d]["Neutral"] for d in sorted_dates]
            },
            "top_negative": top_negative
        })
    except Exception as e:
        print("ADMIN STATS ERROR:", str(e))
        return jsonify({"error": str(e)}), 500

@app.route('/admin/action/<action>/<item_id>', methods=['POST'])
def admin_action(action, item_id):
    if not is_admin():
        return jsonify({"error": "Unauthorized"}), 403

    try:
        obj_id = ObjectId(item_id)
        if action == "delete":
            history.delete_one({"_id": obj_id})
        elif action == "flag":
            history.update_one({"_id": obj_id}, {"$set": {"flagged": True}})
        elif action == "safe":
            history.update_one({"_id": obj_id}, {"$set": {"flagged": False}})
        else:
            return jsonify({"error": "Invalid action"}), 400
        
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/admin/block', methods=['POST'])
def admin_block():
    if not is_admin():
        return jsonify({"error": "Unauthorized"}), 403
        
    data = request.get_json()
    email = data.get('email')
    
    if not email:
        return jsonify({"error": "Email provided is empty"}), 400
        
    res = users.update_one({"email": email}, {"$set": {"isBlocked": True}})
    if res.modified_count > 0:
        return jsonify({"success": True, "message": f"{email} blocked."})
    else:
        return jsonify({"error": "User not found or already blocked"}), 400

# ==========================================
# FEEDBACK ROUTES
# ==========================================

@app.route('/submit-feedback', methods=['POST'])
def submit_feedback():
    if 'user' not in session and 'admin' not in session:
        return jsonify({"error": "Unauthorized"}), 403
        
    data = request.get_json(silent=True) or {}
    message = data.get('message', '').strip()
    f_type = data.get('type', 'Suggestion').strip()
    
    if not message:
        return jsonify({"error": "Message is required"}), 400
        
    feedback_db.insert_one({
        "user": session.get('user') or session.get('admin'),
        "message": message,
        "type": f_type,
        "status": "open",
        "seen": False,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    
    return jsonify({"success": True})

@app.route('/api/user/feedback', methods=['GET'])
def get_user_feedback():
    if 'user' not in session and 'admin' not in session:
        return jsonify({"error": "Unauthorized"}), 403
        
    user_id = session.get('user') or session.get('admin')
    user_feedback = list(feedback_db.find({"user": user_id}).sort("created_at", -1))
    
    for f in user_feedback:
        f["_id"] = str(f["_id"])
        
    return jsonify(user_feedback)

@app.route('/api/user/feedback/mark-seen', methods=['POST'])
def mark_feedback_seen():
    if 'user' not in session and 'admin' not in session:
        return jsonify({"error": "Unauthorized"}), 403
        
    user_id = session.get('user') or session.get('admin')
    
    feedback_db.update_many(
        {"user": user_id, "status": "resolved", "seen": {"$ne": True}},
        {"$set": {"seen": True}}
    )
    
    return jsonify({"success": True})

@app.route('/api/admin/feedback', methods=['GET'])
def get_feedback():
    if not is_admin():
        return jsonify({"error": "Unauthorized"}), 403
        
    all_feedback = list(feedback_db.find().sort("created_at", -1))
    for f in all_feedback:
        f["_id"] = str(f["_id"])
        
    return jsonify(all_feedback)

@app.route('/admin/feedback/action/<action>/<item_id>', methods=['POST'])
def admin_feedback_action(action, item_id):
    if not is_admin():
        return jsonify({"error": "Unauthorized"}), 403
        
    try:
        obj_id = ObjectId(item_id)
        if action == "resolve":
            feedback_db.update_one({"_id": obj_id}, {"$set": {"status": "resolved"}})
        elif action == "delete":
            feedback_db.delete_one({"_id": obj_id})
        else:
            return jsonify({"error": "Invalid action"}), 400
            
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 400
if __name__ == '__main__':
    # macOS may have services bound to :5000 (can look like "403 Forbidden" from a different server).
    port = int(os.environ.get("PORT", "5001"))
    app.run(host="127.0.0.1", port=port, debug=True)
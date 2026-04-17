from flask import Flask, render_template, request, jsonify, redirect, session, make_response
from pymongo import MongoClient
from bson.objectid import ObjectId
import bcrypt
from models.sentiment import get_sentiment

from datetime import datetime
from collections import Counter
import os

app = Flask(__name__)
# Generate a new session key on restart to invalidate cached sessions (forces login)
app.secret_key = os.urandom(24)
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

client = MongoClient("mongodb+srv://admin:admin123@cluster0.f2crrd1.mongodb.net/?retryWrites=true&w=majority")
db = client["sentiment_db"]

users = db["users"]
history = db["history"]

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
        return render_template('index.html')
    return render_template('landing.html')

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
                return render_template('user-login.html', error="Your account has been blocked by an administrator.")
                
            session.clear()
            session['user'] = user['email']
            session['is_admin'] = user.get('isAdmin', False)
            return redirect('/')
        else:
            return render_template('user-login.html', error="Invalid credentials")

    return render_template('user-login.html')

@app.route('/admin-login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not username or not password:
            return render_template('admin-login.html', error="Username and password are required.")

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
            return render_template('admin-login.html', error="Invalid admin credentials.")

        # Handle both hashed and plain passwords
        password_valid = False

        if isinstance(user.get('password'), bytes):
            # bcrypt hashed password
            password_valid = bcrypt.checkpw(password.encode(), user['password'])
        else:
            # plain text password (your current DB)
            password_valid = (password == user.get('password'))

        if not password_valid:
            return render_template('admin-login.html', error="Invalid admin credentials.")

        if user.get('isBlocked', False):
            return render_template('admin-login.html', error="Your account has been blocked.")

        session.clear()
        # Normalize session key
        session['admin'] = user.get('username') or user.get('name')
        return redirect('/admin')

    return render_template('admin-login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = bcrypt.hashpw(request.form['password'].encode(), bcrypt.gensalt())

        existing = users.find_one({"email": email})
        if existing:
            return render_template('register.html', error="User already exists")

        users.insert_one({
            "username": username,
            "email": email,
            "password": password,
            "isAdmin": False,
            "isBlocked": False
        })

        return redirect('/login')

    return render_template('register.html')

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
    if 'user' not in session:
        return redirect('/login')

    user_history = list(history.find(
        {"user": session['user']},
        {"_id": 1, "text": 1, "sentiment": 1, "created_at": 1}
    ))
    
    for item in user_history:
        item['_id'] = str(item['_id'])

    return render_template('dashboard.html', data=user_history)

@app.route('/delete/<id>', methods=['POST'])
def delete_history(id):
    if 'user' not in session:
        return redirect('/login')

    history.delete_one({
        "_id": ObjectId(id),
        "user": session['user']
    })

    return redirect('/dashboard')

@app.route('/analyze', methods=['POST'])
def analyze():
    if 'user' not in session:
        return jsonify({"error": "Login required"})

    user = users.find_one({"email": session['user']})
    if user and user.get('isBlocked', False):
        return jsonify({"error": "Account blocked."})

    data = request.get_json()
    text = data.get('text', '').strip()
    if not text:
        return jsonify({"error": "Empty input"})

    result = normalize_sentiment_label(get_sentiment(text))

    # Insert into history, defaults flagged to False
    history.insert_one({
        "user": session['user'],
        "text": text,
        "sentiment": result,
        "flagged": False,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

    return jsonify({"sentiment": result})


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

    result = normalize_sentiment_label(get_sentiment(text))
    
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

    return render_template('admin.html', users=users_list, admin=session.get('admin'))


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
    return render_template('admin-user.html', email=email, data=user_history, admin=session.get('admin'))

@app.route('/api/admin/stats')
def admin_stats():
    if not is_admin():
        return jsonify({"error": "Unauthorized"}), 403

    all_history = list(history.find())
    
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
    
    for item in all_history:
        s = normalize_sentiment_label(item.get("sentiment", "Neutral"))
        u = item.get("user", "Unknown")
        d = item.get("created_at", "").split(" ")[0] if item.get("created_at") else "Unknown"
        
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
            "text": item.get("text", ""),
            "sentiment": s,
            "flagged": item.get("flagged", False),
            "created_at": item.get("created_at", "")
        })

    # Sort table by date descending
    table_data.sort(key=lambda x: x["created_at"], reverse=True)
    
    # Prepare top negative leaderboard
    top_negative = [{"user": k, "count": v} for k, v in negative_counts.most_common(5) if v > 0]
    
    # Sort dates
    sorted_dates = sorted(date_sentiments.keys())[-14:] # Last 14 dates

    return jsonify({
        "table_data": table_data,
        "pie_chart": sentiments,
        "bar_chart": {
            "labels": [k for k, _ in user_counts.most_common(10)],
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

if __name__ == '__main__':
    # macOS may have services bound to :5000 (can look like "403 Forbidden" from a different server).
    port = int(os.environ.get("PORT", "5001"))
    app.run(host="127.0.0.1", port=port, debug=True)
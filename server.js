const express = require('express');
const mongoose = require('mongoose');
const bcrypt = require('bcrypt');
const jwt = require('jsonwebtoken');
const cors = require('cors');
const path = require('path');
require('dotenv').config();

const User = require('./models/User');
const History = require('./models/History');
const { verifyToken, verifyAdmin } = require('./middlewares/auth');

const app = express();
app.use(cors());
app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

// Use the existing MongoDB Atlas URI from app.py or dotenv
const PORT = process.env.PORT || 3000;
const MONGO_URI = process.env.MONGO_URI || "mongodb+srv://admin:admin123@cluster0.f2crrd1.mongodb.net/sentiment_db?retryWrites=true&w=majority";
const JWT_SECRET = process.env.JWT_SECRET || 'fallback_secret';

mongoose.connect(MONGO_URI, { useNewUrlParser: true, useUnifiedTopology: true })
  .then(() => console.log('Connected to MongoDB'))
  .catch(err => console.error('MongoDB connection error:', err));

// ==========================================
// AUTHENTICATION APIs
// ==========================================

app.post('/api/auth/register', async (req, res) => {
  try {
    const { email, password } = req.body;
    if (!email || !password) return res.status(400).json({ error: 'Email and password required' });

    const existingUser = await User.findOne({ email });
    if (existingUser) return res.status(400).json({ error: 'Email already exists' });

    const hashedPassword = await bcrypt.hash(password, 10);
    const newUser = new User({
      email,
      password: hashedPassword,
      role: 'user'
    });

    await newUser.save();
    res.status(201).json({ message: 'User registered successfully' });
  } catch (error) {
    res.status(500).json({ error: 'Server registration error' });
  }
});

app.post('/api/auth/login', async (req, res) => {
  try {
    const { email, password } = req.body;
    
    // Find user by email
    const user = await User.findOne({ email });
    if (!user) return res.status(400).json({ error: 'Invalid credentials' });

    // Validate using bcrypt.compare
    const isMatch = await bcrypt.compare(password, user.password);
    if (!isMatch) return res.status(400).json({ error: 'Invalid credentials' });

    // Ensure role exists in the document
    const role = user.role || (user.isAdmin ? 'admin' : 'user');

    // Return JWT token
    const token = jwt.sign({ id: user._id, role, email: user.email }, JWT_SECRET, { expiresIn: '24h' });
    
    res.json({ token, role });
  } catch (error) {
    res.status(500).json({ error: 'Server login error' });
  }
});

app.post('/api/auth/admin-login', async (req, res) => {
  try {
    const { email, password } = req.body;
    
    const user = await User.findOne({ email });
    if (!user) return res.status(400).json({ error: 'Invalid credentials' });

    const role = user.role || (user.isAdmin ? 'admin' : 'user');
    
    // if role !== "admin" -> reject
    if (role !== 'admin') {
      return res.status(403).json({ error: 'Access denied. Admin role required.' });
    }

    // Validate password using bcrypt.compare
    const isMatch = await bcrypt.compare(password, user.password);
    if (!isMatch) return res.status(400).json({ error: 'Invalid password' });

    // Return JWT Token
    const token = jwt.sign({ id: user._id, role, email: user.email }, JWT_SECRET, { expiresIn: '24h' });
    
    res.json({ token, role });
  } catch (error) {
    res.status(500).json({ error: 'Server error' });
  }
});

// ==========================================
// PROTECTED APIs
// ==========================================

// Flask Chained Sentiment Engine
app.post('/api/sentiment/analyze', verifyToken, async (req, res) => {
  const { text } = req.body;
  if (!text) return res.status(400).json({ error: 'Text input required' });

  // Fallback timestamp matching python's strftime("%Y-%m-%d %H:%M:%S")
  const formatDate = (date) => {
    return date.toISOString().replace('T', ' ').substring(0, 19);
  };

  try {
    // Attempt forward to Python FLASK engine running locally
    const flaskRequest = await fetch('http://127.0.0.1:5000/service/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text })
    });

    if (!flaskRequest.ok) {
        return res.status(500).json({ error: 'AI Microservice rejected payload' });
    }

    const aiRes = await flaskRequest.json();

    // Persist to MongoDB (Mimicing Flask History insertions for Admins)
    const newHistory = new History({
        user: req.user.email,
        text: text,
        sentiment: aiRes.sentiment,
        flagged: false,
        created_at: formatDate(new Date())
    });
    
    await newHistory.save();

    res.json({ text, sentiment: aiRes.sentiment });

  } catch (err) {
    if (err.cause && err.cause.code === 'ECONNREFUSED') {
         return res.status(503).json({ error: 'AI Sentiment Server is down.' });
    }
    res.status(500).json({ error: 'A Server networking error occurred.' });
  }
});

// Admin fetching users
app.get('/api/admin/users', verifyToken, verifyAdmin, async (req, res) => {
  try {
    const users = await User.find({}, { password: 0 }); // Exclude passwords
    res.json(users);
  } catch (error) {
    res.status(500).json({ error: 'Failed to fetch users' });
  }
});

// ==========================================
// FALLBACK ROUTING for SPA-like feel
// ==========================================
app.get('*', (req, res) => {
  // Let everything fallback to index.html if statically not found so we don't return JSON 404s for views
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

app.listen(PORT, () => {
  console.log(`Node Express Server running on http://localhost:${PORT}`);
});

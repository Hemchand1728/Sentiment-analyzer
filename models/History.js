const mongoose = require('mongoose');

const HistorySchema = new mongoose.Schema({
  user: { type: String, required: true },
  text: { type: String, required: true },
  sentiment: { type: String, required: true },
  flagged: { type: Boolean, default: false },
  created_at: { type: String }
}, { collection: 'history' }); // bind explicitly to the 'history' collection from Flask DB

module.exports = mongoose.model('History', HistorySchema);

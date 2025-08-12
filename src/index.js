// Import modules
const express = require('express');
require('dotenv').config();  // Load .env file variables into process.env
const { getCards } = require('./routes/cards');
const logger = require('./logger');

const app = express();
app.use(express.json());

// Routes
app.get('/cards', getCards);

// Central error handling middleware
app.use((err, req, res, next) => {
  logger.error('Unhandled error:', err);
  res.status(500).json({ error: 'Interner Serverfehler' });
});

// Set up server
const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  logger.info(`Server running on port ${PORT}`);
});

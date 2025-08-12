const Card = require('../models/card');
const logger = require('../logger');

async function getCards(req, res) {
  try {
    const cards = await Card.findAll();
    res.json(cards);
  } catch (error) {
    logger.error('Error fetching cards:', error);
    res.status(500).json({ error: 'Interner Serverfehler' });
  }
}

module.exports = { getCards };

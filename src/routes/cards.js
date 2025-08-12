const logger = require('../logger');
const { getAllCards } = require('../services/cardService');

async function getCards(req, res) {
  try {
    const cards = await getAllCards();
    res.json(cards);
  } catch (error) {
    logger.error('Error fetching cards:', error);
    res.status(500).json({ error: 'Interner Serverfehler' });
  }
}

module.exports = { getCards };

const Card = require('../models/card');

async function getAllCards() {
  return await Card.findAll();
}

module.exports = { getAllCards };

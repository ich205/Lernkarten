const cards = [
  { id: 1, question: 'Was ist 2+2?', answer: '4' },
  { id: 2, question: 'Hauptstadt von Frankreich?', answer: 'Paris' }
];

async function findAll() {
  // Simulate asynchronous database access
  return cards;
}

module.exports = { findAll };

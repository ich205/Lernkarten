// Import modules
const express = require('express');
require('dotenv').config();  // Load .env file variables into process.env
const app = express();

// Set up server
const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});

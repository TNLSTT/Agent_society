const express = require('express');
const path = require('path');
const { spawnSync } = require('child_process');
const fs = require('fs');

const app = express();
const PORT = process.env.PORT || 3000;
const DATA_PATH = path.join(__dirname, 'data', 'simulation_data.json');

function regenerateData() {
  const result = spawnSync('python3', ['scripts/generate_data.py'], {
    cwd: __dirname,
    encoding: 'utf-8',
  });

  if (result.status !== 0) {
    console.error('Simulation generation failed:', result.stderr || result.stdout);
    return false;
  }

  return true;
}

app.use(express.static(path.join(__dirname, 'public')));

app.get('/api/data', (_req, res) => {
  if (!fs.existsSync(DATA_PATH)) {
    const ok = regenerateData();
    if (!ok) {
      return res.status(500).json({ error: 'Failed to generate simulation data.' });
    }
  }

  try {
    const data = JSON.parse(fs.readFileSync(DATA_PATH, 'utf-8'));
    return res.json(data);
  } catch (error) {
    return res.status(500).json({ error: `Failed to load simulation data: ${error.message}` });
  }
});

app.post('/api/rerun', (_req, res) => {
  const ok = regenerateData();
  if (!ok) {
    return res.status(500).json({ error: 'Failed to rerun simulation.' });
  }

  return res.json({ status: 'ok' });
});

app.listen(PORT, () => {
  console.log(`Agent Society web app running at http://localhost:${PORT}`);
});

# Agent Society

## Project Description

Agent Society is now an **NPM web app** that runs the Python simulation and renders an interactive dashboard with visualizations for:

- Total energy over time
- Scarcity pressure over time
- Action distribution (doughnut chart)
- Per-agent energy delta (bar chart)
- Agent-level outcome table

## Quick Start

1. Install dependencies:
   ```bash
   npm install
   ```
2. Start the app:
   ```bash
   npm start
   ```
3. Open:
   ```
   http://localhost:3000
   ```

The server auto-generates simulation data (`data/simulation_data.json`) via Python if it does not exist.

## Useful Scripts

- Generate simulation data only:
  ```bash
  npm run simulate
  ```
- Generate simulation data and start server:
  ```bash
  npm run dev
  ```

## Tech Stack

- **Node.js / Express** for API + static web hosting
- **Python** for simulation execution and data export
- **Chart.js** for frontend visualizations

## License

MIT

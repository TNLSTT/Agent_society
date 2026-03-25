let charts = [];

function clearCharts() {
  charts.forEach((chart) => chart.destroy());
  charts = [];
}

function renderStats(meta) {
  const container = document.getElementById('stats');
  const cards = [
    ['Seed', meta.seed],
    ['Ticks', meta.ticks],
    ['Agents', meta.agent_count],
    ['Gini', meta.gini_coefficient],
    ['Trade actions', meta.trade_actions],
    ['Skills', Object.entries(meta.skill_distribution).map(([k, v]) => `${k}:${v}`).join(' | ')],
  ];

  container.innerHTML = cards
    .map(
      ([label, value]) =>
        `<article class="stat-card"><div class="stat-label">${label}</div><div class="stat-value">${value}</div></article>`
    )
    .join('');
}

function renderTable(agents) {
  document.getElementById('agentRows').innerHTML = agents
    .map(
      (agent) => `
      <tr>
        <td>#${agent.agent_id}</td>
        <td><span class="badge">${agent.skill}</span></td>
        <td>${agent.final_energy}</td>
        <td>${agent.reputation.toFixed(2)}</td>
        <td>${agent.trade_count}</td>
        <td>${agent.dominant_action}</td>
      </tr>
    `
    )
    .join('');
}

function renderCharts(data) {
  clearCharts();
  const ticks = data.ticks.map((t) => t.tick);

  charts.push(
    new Chart(document.getElementById('energyChart'), {
      type: 'line',
      data: {
        labels: ticks,
        datasets: [{
          label: 'Total Energy',
          data: data.ticks.map((t) => t.total_energy),
          borderColor: '#7dd3fc',
          fill: true,
          backgroundColor: 'rgba(125, 211, 252, 0.16)',
          tension: 0.25,
        }],
      },
    })
  );

  charts.push(
    new Chart(document.getElementById('scarcityChart'), {
      type: 'line',
      data: {
        labels: ticks,
        datasets: [{
          label: 'Scarcity',
          data: data.ticks.map((t) => t.scarcity),
          borderColor: '#c084fc',
          fill: true,
          backgroundColor: 'rgba(192, 132, 252, 0.14)',
          tension: 0.25,
        }],
      },
    })
  );

  charts.push(
    new Chart(document.getElementById('actionChart'), {
      type: 'doughnut',
      data: {
        labels: data.action_counts.map((a) => a.action),
        datasets: [{
          data: data.action_counts.map((a) => a.count),
          backgroundColor: ['#38bdf8', '#a78bfa', '#f59e0b', '#22c55e', '#f43f5e'],
        }],
      },
    })
  );

  charts.push(
    new Chart(document.getElementById('deltaChart'), {
      type: 'bar',
      data: {
        labels: data.energy_delta.map((d) => `A${d.agent_id}`),
        datasets: [{
          label: 'Energy Δ',
          data: data.energy_delta.map((d) => d.delta),
          backgroundColor: data.energy_delta.map((d) => (d.delta >= 0 ? '#22c55e' : '#f43f5e')),
        }],
      },
      options: {
        scales: {
          y: {
            beginAtZero: true,
          },
        },
      },
    })
  );
}

async function loadData() {
  const response = await fetch('/api/data');
  if (!response.ok) {
    throw new Error('Unable to load data');
  }

  const data = await response.json();
  renderStats(data.meta);
  renderTable(data.agents);
  renderCharts(data);
}

document.getElementById('rerunBtn').addEventListener('click', async () => {
  const btn = document.getElementById('rerunBtn');
  btn.disabled = true;
  btn.textContent = 'Running...';
  try {
    const response = await fetch('/api/rerun', { method: 'POST' });
    if (!response.ok) {
      throw new Error('Rerun failed');
    }
    await loadData();
  } finally {
    btn.disabled = false;
    btn.textContent = '🔁 Rerun Simulation';
  }
});

loadData().catch((err) => {
  console.error(err);
  alert('Failed to load simulation dashboard. Check server logs.');
});

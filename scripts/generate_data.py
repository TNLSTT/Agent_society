#!/usr/bin/env python3
"""Run simulation and export chart-friendly JSON for the web UI."""

from __future__ import annotations

import json
import random
import sqlite3
from collections import Counter
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from simulation import DB_PATH, SEED, TICKS, gini_coefficient, run_simulation

OUTPUT_PATH = Path("data/simulation_data.json")


def main() -> None:
    rng = random.Random(SEED)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row

    try:
        agents = run_simulation(connection, rng, ticks=TICKS)

        tick_rows = connection.execute(
            "SELECT tick, scarcity, total_energy FROM ticks ORDER BY tick"
        ).fetchall()

        action_rows = connection.execute(
            "SELECT action, COUNT(*) AS count FROM tick_logs GROUP BY action ORDER BY count DESC"
        ).fetchall()

        agent_rows = connection.execute(
            "SELECT agent_id, skill, initial_energy FROM agents ORDER BY agent_id"
        ).fetchall()

        agent_summary = []
        for agent in agents:
            agent_summary.append(
                {
                    "agent_id": agent.agent_id,
                    "skill": agent.skill,
                    "final_energy": agent.energy,
                    "reputation": round(agent.reputation, 3),
                    "trade_count": agent.trade_count,
                    "dominant_action": agent.action_counts.most_common(1)[0][0]
                    if agent.action_counts
                    else "none",
                }
            )

        initial_energy_map = {row["agent_id"]: row["initial_energy"] for row in agent_rows}
        energy_delta = [
            {
                "agent_id": agent["agent_id"],
                "skill": agent["skill"],
                "initial_energy": initial_energy_map[agent["agent_id"]],
                "final_energy": agent["final_energy"],
                "delta": agent["final_energy"] - initial_energy_map[agent["agent_id"]],
            }
            for agent in agent_summary
        ]

        payload = {
            "meta": {
                "seed": SEED,
                "ticks": TICKS,
                "agent_count": len(agents),
                "gini_coefficient": round(gini_coefficient([a.energy for a in agents]), 4),
                "skill_distribution": dict(Counter(agent.skill for agent in agents)),
                "trade_actions": sum(agent.action_counts["trade"] for agent in agents),
            },
            "ticks": [
                {
                    "tick": row["tick"],
                    "scarcity": row["scarcity"],
                    "total_energy": row["total_energy"],
                }
                for row in tick_rows
            ],
            "action_counts": [{"action": row["action"], "count": row["count"]} for row in action_rows],
            "agents": agent_summary,
            "energy_delta": energy_delta,
        }

        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"Wrote {OUTPUT_PATH}")
    finally:
        connection.close()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Minimal SQLite-backed multi-agent resource simulation."""

from __future__ import annotations

import random
import sqlite3
from collections import Counter, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Deque, Dict, List, Optional, Tuple

DB_PATH = Path("simulation.db")
TICKS = 100
AGENT_COUNT = 8
MEMORY_LIMIT = 5
NEIGHBOR_COUNT = 3
SEED = 7

GATHER_GAIN = 8
GATHER_COST = 2
GATHER_TIME = 1

CONVERT_COST = 6
CONVERT_RETURN = 16
CONVERT_TIME = 2

TRADE_SEND = 5
TRADE_PRICE = 6
TRADE_COMM_COST = 1
TRADE_TIME = 1

IDLE_COST = 1
IDLE_TIME = 1

ENV_DECAY = 1
SKILLS = ("gather", "convert", "trade")


@dataclass
class Agent:
    agent_id: int
    skill: str
    energy: int
    memory_limit: int = MEMORY_LIMIT
    reputation: float = 0.0
    memory: Deque[str] = field(default_factory=lambda: deque(maxlen=MEMORY_LIMIT))
    action_counts: Counter = field(default_factory=Counter)
    trade_count: int = 0

    def observe(self, population: List["Agent"], rng: random.Random) -> Dict[str, object]:
        candidates = [agent for agent in population if agent.agent_id != self.agent_id]
        visible_agents = rng.sample(candidates, k=min(NEIGHBOR_COUNT, len(candidates)))
        return {
            "self": {
                "agent_id": self.agent_id,
                "energy": self.energy,
                "skill": self.skill,
                "reputation": round(self.reputation, 2),
                "memory": list(self.memory),
            },
            "nearby": [
                {
                    "agent_id": agent.agent_id,
                    "energy": agent.energy,
                    "skill": agent.skill,
                    "reputation": round(agent.reputation, 2),
                }
                for agent in visible_agents
            ],
        }

    def decide(self, observation: Dict[str, object]) -> Tuple[str, Optional[int]]:
        own_state = observation["self"]
        nearby = observation["nearby"]
        energy = int(own_state["energy"])

        if energy <= 12:
            return "gather", None

        if self.skill == "trade" and energy > TRADE_SEND + TRADE_COMM_COST + 8:
            needy = [other for other in nearby if other["energy"] < 40]
            if needy:
                target = min(needy, key=lambda other: (other["energy"], other["agent_id"]))
                return "trade", int(target["agent_id"])

        if self.skill == "convert" and energy >= CONVERT_COST + 10:
            return "convert", None

        if self.skill == "gather":
            if energy < 90 or not nearby:
                return "gather", None
            richest_neighbor = max(nearby, key=lambda other: other["energy"])
            if richest_neighbor["energy"] > energy + 30 and energy > TRADE_SEND + TRADE_COMM_COST + 10:
                return "trade", int(richest_neighbor["agent_id"])
            return "gather", None

        if self.skill == "trade" and nearby:
            richest_neighbor = max(nearby, key=lambda other: other["energy"])
            if richest_neighbor["energy"] > energy + 20 and energy > TRADE_SEND + TRADE_COMM_COST + 10:
                return "trade", int(richest_neighbor["agent_id"])

        if energy >= CONVERT_COST + 20:
            return "convert", None

        if energy <= 25:
            return "gather", None

        return "idle", None


def initialize_database(connection: sqlite3.Connection) -> None:
    cursor = connection.cursor()
    cursor.executescript(
        """
        DROP TABLE IF EXISTS agents;
        DROP TABLE IF EXISTS tick_logs;
        DROP TABLE IF EXISTS ticks;

        CREATE TABLE agents (
            agent_id INTEGER PRIMARY KEY,
            skill TEXT NOT NULL,
            initial_energy INTEGER NOT NULL
        );

        CREATE TABLE ticks (
            tick INTEGER PRIMARY KEY,
            scarcity INTEGER NOT NULL,
            total_energy INTEGER NOT NULL
        );

        CREATE TABLE tick_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tick INTEGER NOT NULL,
            agent_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            target_agent_id INTEGER,
            energy_before INTEGER NOT NULL,
            energy_after INTEGER NOT NULL,
            time_penalty INTEGER NOT NULL,
            interaction TEXT,
            FOREIGN KEY(agent_id) REFERENCES agents(agent_id)
        );
        """
    )
    connection.commit()


def create_agents(connection: sqlite3.Connection, rng: random.Random) -> List[Agent]:
    agents: List[Agent] = []
    skills = [rng.choice(SKILLS) for _ in range(AGENT_COUNT)]
    cursor = connection.cursor()
    for agent_id in range(1, AGENT_COUNT + 1):
        skill = skills[agent_id - 1]
        energy = rng.randint(50, 150)
        agent = Agent(agent_id=agent_id, skill=skill, energy=energy)
        agent.memory.append(f"spawn:{energy}")
        agents.append(agent)
        cursor.execute(
            "INSERT INTO agents (agent_id, skill, initial_energy) VALUES (?, ?, ?)",
            (agent.agent_id, agent.skill, energy),
        )
    connection.commit()
    return agents


def apply_action(
    connection: sqlite3.Connection,
    tick: int,
    agent: Agent,
    action: str,
    target_id: Optional[int],
    population_by_id: Dict[int, Agent],
) -> None:
    energy_before = agent.energy
    interaction = ""
    time_penalty = IDLE_TIME

    if action == "gather":
        agent.energy -= GATHER_COST
        agent.energy += GATHER_GAIN
        time_penalty = GATHER_TIME
        interaction = f"gained:{GATHER_GAIN - GATHER_COST}"
        agent.reputation += 0.05
    elif action == "convert":
        agent.energy -= CONVERT_COST
        agent.energy += CONVERT_RETURN
        time_penalty = CONVERT_TIME
        interaction = f"converted:{CONVERT_RETURN - CONVERT_COST}"
        agent.reputation += 0.1
    elif action == "trade":
        time_penalty = TRADE_TIME
        if target_id is not None and target_id in population_by_id and target_id != agent.agent_id:
            target = population_by_id[target_id]
            total_cost = TRADE_SEND + TRADE_COMM_COST
            if agent.energy > total_cost:
                agent.energy -= total_cost
                target.energy += TRADE_SEND
                agent.energy += TRADE_PRICE
                interaction = f"sold:{TRADE_SEND}:to:{target_id}:price:{TRADE_PRICE}"
                agent.trade_count += 1
                target.trade_count += 1
                agent.reputation += 0.2
                target.reputation += 0.05
                target.memory.append(f"tick:{tick}:bought:{TRADE_SEND}:from:{agent.agent_id}")
            else:
                agent.energy -= TRADE_COMM_COST
                interaction = f"failed_trade:{target_id}:insufficient_energy"
                agent.reputation -= 0.1
        else:
            agent.energy -= TRADE_COMM_COST
            interaction = "failed_trade:no_target"
            agent.reputation -= 0.1
    else:
        action = "idle"
        agent.energy -= IDLE_COST
        interaction = "idle"
        agent.reputation -= 0.02

    agent.energy = max(agent.energy, 0)
    agent.action_counts[action] += 1
    agent.memory.append(f"tick:{tick}:{interaction}")

    connection.execute(
        """
        INSERT INTO tick_logs (
            tick, agent_id, action, target_agent_id, energy_before, energy_after, time_penalty, interaction
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (tick, agent.agent_id, action, target_id, energy_before, agent.energy, time_penalty, interaction),
    )


def update_environment(connection: sqlite3.Connection, tick: int, agents: List[Agent]) -> None:
    for agent in agents:
        agent.energy = max(agent.energy - ENV_DECAY, 0)
        agent.memory.append(f"tick:{tick}:decay:{ENV_DECAY}")

    total_energy = sum(agent.energy for agent in agents)
    scarcity = max(0, 1000 - total_energy)
    connection.execute(
        "INSERT INTO ticks (tick, scarcity, total_energy) VALUES (?, ?, ?)",
        (tick, scarcity, total_energy),
    )
    connection.commit()


def gini_coefficient(values: List[int]) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    total = sum(sorted_values)
    if total == 0:
        return 0.0
    weighted_sum = sum((index + 1) * value for index, value in enumerate(sorted_values))
    return (2 * weighted_sum) / (len(values) * total) - (len(values) + 1) / len(values)


def summarize(agents: List[Agent]) -> None:
    energies = [agent.energy for agent in agents]
    specialization = {
        agent.agent_id: agent.action_counts.most_common(1)[0][0] if agent.action_counts else "none"
        for agent in agents
    }
    skill_totals = Counter(agent.skill for agent in agents)
    dominant_actions = Counter(specialization.values())
    total_trades = sum(agent.action_counts["trade"] for agent in agents)

    print("=== Final Agent States ===")
    for agent in agents:
        print(
            f"agent={agent.agent_id} skill={agent.skill} energy={agent.energy} "
            f"reputation={agent.reputation:.2f} dominant_action={specialization[agent.agent_id]} "
            f"memory={list(agent.memory)}"
        )

    print("\n=== Summary Metrics ===")
    print(f"energy_distribution={energies}")
    print(f"gini_coefficient={gini_coefficient(energies):.4f}")
    print(f"number_of_trades={total_trades}")
    print(f"skill_distribution={dict(skill_totals)}")
    print(f"specialization_patterns={dict(dominant_actions)}")


def main() -> None:
    rng = random.Random(SEED)
    connection = sqlite3.connect(DB_PATH)
    try:
        initialize_database(connection)
        agents = create_agents(connection, rng)
        population_by_id = {agent.agent_id: agent for agent in agents}

        for tick in range(TICKS):
            for agent in agents:
                observation = agent.observe(agents, rng)
                action, target_id = agent.decide(observation)
                apply_action(connection, tick, agent, action, target_id, population_by_id)
            update_environment(connection, tick, agents)

        summarize(agents)
    finally:
        connection.close()


if __name__ == "__main__":
    main()

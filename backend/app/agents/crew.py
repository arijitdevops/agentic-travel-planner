"""Crew assembly.

``TravelPlanningCrew`` wires six agents into a sequential CrewAI process::

    profile -> research -> flights -> hotels -> itinerary -> budget

``RefinementCrew`` is a single concierge agent used for chat follow-ups.
Agent and task wording lives in ``config/agents.yaml`` and ``config/tasks.yaml``.
"""

from __future__ import annotations

import warnings
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from crewai import Agent, BaseLLM, Crew, Process, Task
from crewai.tasks.task_output import TaskOutput
from pydantic import BaseModel

from app.agents.schemas import (
    BudgetBreakdown,
    DestinationResearch,
    FlightSelection,
    HotelSelection,
    Itinerary,
    RefinementResult,
    TravelerProfile,
)
from app.agents.tools import ToolContext, build_tools

CONFIG_DIR = Path(__file__).parent / "config"

# CrewAI warns that plain function callbacks prevent checkpointing; we don't checkpoint.
warnings.filterwarnings("ignore", message=".*callbacks cannot be serialized.*")


@lru_cache
def load_config() -> tuple[dict[str, Any], dict[str, Any]]:
    agents = yaml.safe_load((CONFIG_DIR / "agents.yaml").read_text(encoding="utf-8"))
    tasks = yaml.safe_load((CONFIG_DIR / "tasks.yaml").read_text(encoding="utf-8"))
    return agents, tasks


@dataclass(frozen=True)
class PlanningStep:
    task_key: str
    agent_key: str
    output_model: type[BaseModel]
    context: tuple[str, ...]
    start_message: str
    done_message: str


PLANNING_STEPS: list[PlanningStep] = [
    PlanningStep("profile_task", "traveler_profiler", TravelerProfile, (),
                 "Analysing your preferences and constraints", "Traveler profile ready"),
    PlanningStep("research_task", "destination_researcher", DestinationResearch, ("profile_task",),
                 "Researching destinations, weather and local tips", "Destination research complete"),
    PlanningStep("flight_task", "flight_specialist", FlightSelection, ("profile_task",),
                 "Comparing flight options for each leg", "Flights selected"),
    PlanningStep("hotel_task", "hotel_specialist", HotelSelection, ("profile_task", "research_task"),
                 "Shortlisting hotels in the best areas", "Hotels selected"),
    PlanningStep("itinerary_task", "itinerary_planner", Itinerary,
                 ("profile_task", "research_task", "flight_task", "hotel_task"),
                 "Designing your day-by-day itinerary", "Itinerary drafted"),
    PlanningStep("budget_task", "budget_analyst", BudgetBreakdown, ("flight_task", "hotel_task", "itinerary_task"),
                 "Checking the plan against your budget", "Budget breakdown ready"),
]


def agent_labels() -> dict[str, str]:
    agents_cfg, _ = load_config()
    return {key: cfg["role"] for key, cfg in agents_cfg.items()}


def _make_agent(key: str, llm: BaseLLM, tools: list, max_iter: int, verbose: bool) -> Agent:
    agents_cfg, _ = load_config()
    cfg = agents_cfg[key]
    return Agent(
        role=cfg["role"],
        goal=cfg["goal"].strip(),
        backstory=cfg["backstory"].strip(),
        llm=llm,
        tools=tools,
        allow_delegation=False,
        max_iter=max_iter,
        verbose=verbose,
    )


def _make_task(key: str, agent: Agent, output_model: type[BaseModel], context: list[Task]) -> Task:
    _, tasks_cfg = load_config()
    cfg = tasks_cfg[key]
    return Task(
        name=key,
        description=cfg["description"].strip(),
        expected_output=cfg["expected_output"].strip(),
        agent=agent,
        context=context or None,
        output_pydantic=output_model,
    )


class TravelPlanningCrew:
    """Six specialists in a sequential process."""

    def __init__(
        self,
        llm: BaseLLM,
        tool_ctx: ToolContext,
        task_callback: Callable[[TaskOutput], None] | None = None,
        max_iter: int = 8,
        verbose: bool = False,
    ) -> None:
        labels = agent_labels()
        tools = build_tools(tool_ctx, labels)
        self.agents: dict[str, Agent] = {}
        self.tasks: dict[str, Task] = {}
        for step in PLANNING_STEPS:
            agent = _make_agent(step.agent_key, llm, tools[step.agent_key], max_iter, verbose)
            self.agents[step.agent_key] = agent
            self.tasks[step.task_key] = _make_task(
                step.task_key, agent, step.output_model, [self.tasks[c] for c in step.context]
            )
        kwargs: dict[str, Any] = {}
        if task_callback is not None:
            kwargs["task_callback"] = task_callback
        self.crew = Crew(
            agents=list(self.agents.values()),
            tasks=list(self.tasks.values()),
            process=Process.sequential,
            verbose=verbose,
            **kwargs,
        )

    def run(self, inputs: dict[str, Any]) -> dict[str, BaseModel]:
        result = self.crew.kickoff(inputs=inputs)
        outputs: dict[str, BaseModel] = {}
        for step, task_output in zip(PLANNING_STEPS, result.tasks_output, strict=True):
            outputs[step.task_key] = coerce_output(task_output, step.output_model)
        return outputs


class RefinementCrew:
    def __init__(self, llm: BaseLLM, tool_ctx: ToolContext, max_iter: int = 8, verbose: bool = False) -> None:
        tools = build_tools(tool_ctx, agent_labels())
        self.agent = _make_agent("trip_concierge", llm, tools["trip_concierge"], max_iter, verbose)
        self.task = _make_task("refine_task", self.agent, RefinementResult, [])
        self.crew = Crew(agents=[self.agent], tasks=[self.task], process=Process.sequential, verbose=verbose)

    def run(self, inputs: dict[str, Any]) -> RefinementResult:
        result = self.crew.kickoff(inputs=inputs)
        output = coerce_output(result.tasks_output[0], RefinementResult)
        assert isinstance(output, RefinementResult)
        return output


def coerce_output(task_output: TaskOutput, model: type[BaseModel]) -> BaseModel:
    """Return the task's pydantic output, parsing raw JSON as a fallback."""
    if isinstance(task_output.pydantic, model):
        return task_output.pydantic
    if task_output.json_dict:
        return model.model_validate(task_output.json_dict)
    raw = (task_output.raw or "").strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        raw = raw[raw.find("{"):]
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"{model.__name__}: agent did not return structured output")
    return model.model_validate_json(raw[start : end + 1])

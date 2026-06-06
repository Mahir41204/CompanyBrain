from __future__ import annotations

import argparse
import json
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from .connectors import NotionConnector
from .coverage import CoverageService
from .core.graph import BrainGraph
from .decision_engine import DecisionEngine
from .execution.planner import ExecutionPlanner
from .ingestion import IngestionService
from .learning import LearningService
from .memory.event_store import Event, EventStore
from .memory.health import MemoryHealth
from .memory.process_mining import ProcessMiner
from .models import skill_summary
from .product import (
    CoverageViewService,
    DashboardService,
    EvidenceExplorerService,
    GraphViewService,
    PeopleExplorerService,
    PeopleRiskService,
    ProcessExplorerService,
    RiskCenterService,
    SimulationService,
    SourceDashboardService,
)
from .reasoning import (
    BrainQueryEngine,
    ConfidenceRanker,
    ConflictDetector,
    ConflictResolver,
    MemoryExplainer,
    OrganizationalEvolution,
    OrganizationalSimulator,
)
from .reasoning.semantic_search import SemanticSearchService
from .repository import SkillRepository
from .runtime import AgentRuntime
from .storage import (
    DiscoveryRepository,
    EdgeRepository,
    EntityRepository,
    EvidenceRepository,
    LLMDiscoveryRepository,
    SnapshotRepository,
    SourceSyncRepository,
)


STATIC_DIR = Path(__file__).resolve().parent / "static"


def make_handler(data_dir: str | Path) -> type[BaseHTTPRequestHandler]:
    repository = SkillRepository(data_dir)
    decision_engine = DecisionEngine()
    learning_service = LearningService(repository)
    ingestion_service = IngestionService(repository)
    coverage_service = CoverageService(repository)
    entity_repository = EntityRepository(data_dir)
    edge_repository = EdgeRepository(data_dir)
    evidence_repository = EvidenceRepository(data_dir)
    discovery_repository = DiscoveryRepository(data_dir)
    llm_discovery_repository = LLMDiscoveryRepository(data_dir)
    snapshot_repository = SnapshotRepository(data_dir)
    source_repository = SourceSyncRepository(data_dir)
    event_store = EventStore(data_dir)
    process_miner = ProcessMiner()
    notion_connector = NotionConnector(data_dir=data_dir, sources=source_repository)

    def load_graph() -> BrainGraph:
        return BrainGraph(
            entities=entity_repository.list_entities(),
            edges=edge_repository.list_edges(),
            evidence=evidence_repository.list_evidence(),
        )

    def query_engine() -> BrainQueryEngine:
        return BrainQueryEngine(load_graph(), snapshot_repository.list_snapshots())

    class CompanyBrainHandler(BaseHTTPRequestHandler):
        server_version = "CompanyBrain/0.1"

        def do_OPTIONS(self) -> None:
            self.send_response(HTTPStatus.NO_CONTENT)
            self._send_common_headers("application/json", 0)
            self.end_headers()

        def do_GET(self) -> None:
            try:
                parsed = urlparse(self.path)
                path = unquote(parsed.path)
                parts = self._parts(path)
                query = parse_qs(parsed.query)

                if path == "/":
                    self._send_file(STATIC_DIR / "index.html")
                    return
                if parts and parts[0] == "static":
                    self._send_static(parts[1:])
                    return
                if parts == ["health"]:
                    self._send_json({"status": "ok"})
                    return
                if parts == ["brain", "skills"]:
                    skills = [skill_summary(skill) for skill in repository.list_skills()]
                    self._send_json({"skills": skills})
                    return
                if len(parts) == 3 and parts[:2] == ["brain", "skills"]:
                    self._send_json(repository.get_skill(parts[2]))
                    return
                if parts == ["brain", "candidates"]:
                    self._send_json({"candidates": repository.list_candidates()})
                    return
                if parts == ["brain", "coverage"]:
                    self._send_json(coverage_service.compute())
                    return
                if parts == ["brain", "dashboard"]:
                    self._send_json(
                        DashboardService(
                            load_graph(),
                            snapshot_repository.list_snapshots(),
                            coverage_service.compute(),
                        ).build()
                    )
                    return
                if parts == ["brain", "search"]:
                    search_query = self._query_value(query, "q") or self._query_value(query, "query")
                    if not search_query:
                        raise ValueError("Query parameter q is required")
                    limit = int(self._query_value(query, "limit") or "8")
                    self._send_json(query_engine().search(search_query, limit=limit))
                    return
                if parts == ["brain", "semantic-search"]:
                    search_query = self._query_value(query, "q") or self._query_value(query, "query")
                    if not search_query:
                        raise ValueError("Query parameter q is required")
                    limit = int(self._query_value(query, "limit") or "10")
                    self._send_json(SemanticSearchService(load_graph()).search(search_query, limit=limit))
                    return
                if parts == ["brain", "graph"]:
                    self._send_json(load_graph().to_dict())
                    return
                if parts == ["brain", "graph", "view"]:
                    self._send_json(GraphViewService(load_graph(), snapshot_repository.list_snapshots()).build())
                    return
                if parts == ["brain", "graph", "entities"]:
                    self._send_json({"entities": [entity.to_dict() for entity in entity_repository.list_entities()]})
                    return
                if parts == ["brain", "graph", "edges"]:
                    self._send_json({"edges": [edge.to_dict() for edge in edge_repository.list_edges()]})
                    return
                if parts == ["brain", "graph", "evidence"]:
                    self._send_json(
                        {"evidence": [evidence.to_dict() for evidence in evidence_repository.list_evidence()]}
                    )
                    return
                if parts == ["brain", "graph", "explain"]:
                    search_query = self._query_value(query, "q") or self._query_value(query, "query")
                    if not search_query:
                        raise ValueError("Query parameter q is required")
                    at = self._query_value(query, "at")
                    self._send_json(MemoryExplainer(load_graph(), snapshot_repository.list_snapshots()).explain(search_query, at))
                    return
                if len(parts) == 4 and parts[:3] == ["brain", "graph", "neighbors"]:
                    self._send_json({"neighbors": load_graph().neighbors(parts[3])})
                    return
                if parts == ["brain", "graph", "path"]:
                    source_id = self._query_value(query, "from") or self._query_value(query, "source")
                    target_id = self._query_value(query, "to") or self._query_value(query, "target")
                    if not source_id or not target_id:
                        raise ValueError("Query parameters from and to are required")
                    path_result = load_graph().path(source_id, target_id)
                    self._send_json({"path": path_result})
                    return
                if parts == ["brain", "processes", "flows"]:
                    self._send_json(process_miner.discover_flow(event_store.list_events()))
                    return
                if parts == ["brain", "discoveries"]:
                    self._send_json(
                        {"discoveries": [discovery.to_dict() for discovery in discovery_repository.list_discoveries()]}
                    )
                    return
                if parts == ["brain", "llm-discoveries"]:
                    self._send_json({"discoveries": llm_discovery_repository.list_results()})
                    return
                if parts == ["brain", "processes"]:
                    self._send_json(
                        ProcessExplorerService(
                            load_graph(),
                            discovery_repository.list_discoveries(),
                            llm_discovery_repository.list_results(),
                        ).build()
                    )
                    return
                if parts == ["brain", "people"]:
                    self._send_json(PeopleExplorerService(load_graph()).build())
                    return
                if parts == ["brain", "people-risk"]:
                    target = self._query_value(query, "target") or self._query_value(query, "q")
                    self._send_json(PeopleRiskService(load_graph()).build(target))
                    return
                if parts == ["brain", "evidence"]:
                    search_query = self._query_value(query, "q") or self._query_value(query, "query")
                    self._send_json(EvidenceExplorerService(load_graph(), llm_discovery_repository.list_results()).build(search_query))
                    return
                if parts == ["brain", "risks"]:
                    self._send_json(RiskCenterService(load_graph(), snapshot_repository.list_snapshots(), coverage_service.compute()).build())
                    return
                if parts == ["brain", "coverage", "view"]:
                    self._send_json(CoverageViewService(load_graph(), coverage_service.compute()).build())
                    return
                if parts == ["brain", "sources"]:
                    self._send_json(SourceDashboardService(source_repository, notion_connector).build())
                    return
                if parts == ["brain", "snapshots"]:
                    entity_id = self._query_value(query, "entity_id")
                    self._send_json(
                        {"snapshots": [snapshot.to_dict() for snapshot in snapshot_repository.list_snapshots(entity_id)]}
                    )
                    return
                if parts == ["brain", "conflicts"]:
                    snapshots = snapshot_repository.list_snapshots()
                    conflicts = ConflictDetector().detect(snapshots)
                    resolver = ConflictResolver()
                    self._send_json(
                        {
                            "conflicts": [conflict.to_dict() for conflict in conflicts],
                            "resolution_suggestions": [
                                resolver.suggest(conflict, snapshots) for conflict in conflicts
                            ],
                        }
                    )
                    return
                if parts == ["brain", "confidence", "rankings"]:
                    ranked = ConfidenceRanker().rank_entities(entity_repository.list_entities())
                    self._send_json({"rankings": ranked})
                    return
                if parts == ["brain", "query", "owner"]:
                    self._send_json(query_engine().find_owner(self._required_query(query)))
                    return
                if parts == ["brain", "query", "dependencies"]:
                    depth = int(self._query_value(query, "depth") or "3")
                    self._send_json(query_engine().find_dependencies(self._required_query(query), max_depth=depth))
                    return
                if parts == ["brain", "query", "affected"]:
                    depth = int(self._query_value(query, "depth") or "4")
                    self._send_json(query_engine().find_affected(self._required_query(query), max_depth=depth))
                    return
                if parts == ["brain", "query", "trace"]:
                    self._send_json(query_engine().trace_decision(self._required_query(query)))
                    return
                if parts == ["brain", "query", "timeline"]:
                    search_query = self._query_value(query, "q") or self._query_value(query, "entity_id")
                    if not search_query:
                        raise ValueError("Query parameter q or entity_id is required")
                    self._send_json(query_engine().timeline(search_query))
                    return
                if parts == ["brain", "memory", "health"]:
                    as_of = self._query_value(query, "as_of")
                    stale_after_days = int(self._query_value(query, "stale_after_days") or "180")
                    expired_after_days = int(self._query_value(query, "expired_after_days") or "365")
                    health = MemoryHealth(
                        entity_repository.list_entities(),
                        evidence_repository.list_evidence(),
                        snapshot_repository.list_snapshots(),
                    )
                    self._send_json(
                        health.assess(
                            as_of=as_of,
                            stale_after_days=stale_after_days,
                            expired_after_days=expired_after_days,
                        )
                    )
                    return
                if parts == ["brain", "evolution"]:
                    entity_id = self._query_value(query, "entity_id")
                    evolution = OrganizationalEvolution(load_graph(), snapshot_repository.list_snapshots())
                    self._send_json(evolution.timeline(entity_id))
                    return

                self._send_error(HTTPStatus.NOT_FOUND, "Not found")
            except KeyError as exc:
                self._send_error(HTTPStatus.NOT_FOUND, str(exc))
            except ValueError as exc:
                self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            except Exception as exc:
                self._send_error(HTTPStatus.INTERNAL_SERVER_ERROR, str(exc))

        def do_POST(self) -> None:
            try:
                parsed = urlparse(self.path)
                parts = self._parts(unquote(parsed.path))
                payload = self._read_json()

                if len(parts) == 3 and parts[:2] == ["brain", "execute"]:
                    skill_id = parts[2]
                    context = payload.get("context", payload)
                    if not isinstance(context, dict):
                        raise ValueError("Execution context must be a JSON object")
                    skill = repository.get_skill(skill_id)
                    decision = decision_engine.execute(skill, context)
                    execution = learning_service.record_execution(skill_id, context, decision)
                    decision["execution_id"] = execution["execution_id"]
                    self._send_json(decision)
                    return

                if parts == ["brain", "learn"]:
                    self._send_json(learning_service.submit_outcome(payload))
                    return

                if parts == ["brain", "ingest"]:
                    self._send_json(ingestion_service.ingest(payload), status=HTTPStatus.CREATED)
                    return

                if parts == ["brain", "events"]:
                    event_payloads = payload.get("events")
                    if event_payloads is None:
                        event_payloads = [payload]
                    if not isinstance(event_payloads, list):
                        raise ValueError("events must be a list")
                    events = [Event.from_dict(item) for item in event_payloads]
                    event_store.append_many(events)
                    self._send_json({"events": [event.to_dict() for event in events]}, status=HTTPStatus.CREATED)
                    return

                if parts == ["brain", "plan"]:
                    query = str(payload.get("query", "")).strip()
                    if not query:
                        raise ValueError("query is required")
                    self._send_json(ExecutionPlanner(load_graph()).build_plan(query))
                    return

                if parts == ["brain", "simulate"]:
                    query = str(payload.get("query", "")).strip()
                    if not query:
                        raise ValueError("query is required")
                    self._send_json(OrganizationalSimulator(load_graph()).simulate_removal(query))
                    return

                if parts == ["brain", "simulation", "run"]:
                    self._send_json(SimulationService(load_graph()).run(payload))
                    return

                if parts == ["brain", "connectors", "notion", "sync"]:
                    api_key = payload.get("api_key")
                    connector = NotionConnector(
                        data_dir=data_dir,
                        api_key=str(api_key) if api_key else None,
                        sources=source_repository,
                    )
                    self._send_json(connector.sync(payload), status=HTTPStatus.CREATED)
                    return

                if parts == ["brain", "agent-tasks"]:
                    goal = str(payload.get("goal", "")).strip()
                    if not goal:
                        raise ValueError("goal is required")
                    context = payload.get("context", {})
                    if not isinstance(context, dict):
                        raise ValueError("context must be an object")
                    execute_task = bool(payload.get("execute", True))
                    runtime = AgentRuntime(load_graph(), repository, decision_engine, learning_service)
                    task = runtime.run(goal, context, execute=execute_task)
                    response = {"task": task.to_dict()}
                    if payload.get("outcome"):
                        response["learning"] = runtime.learn(task, str(payload["outcome"]), payload.get("notes"))
                    self._send_json(response, status=HTTPStatus.CREATED)
                    return

                if len(parts) == 4 and parts[:2] == ["brain", "candidates"] and parts[3] == "approve":
                    self._send_json({"skill": repository.approve_candidate(parts[2])})
                    return

                if len(parts) == 4 and parts[:2] == ["brain", "candidates"] and parts[3] == "reject":
                    note = payload.get("note") if isinstance(payload, dict) else None
                    self._send_json({"candidate": repository.update_candidate_status(parts[2], "rejected", note)})
                    return

                self._send_error(HTTPStatus.NOT_FOUND, "Not found")
            except KeyError as exc:
                self._send_error(HTTPStatus.NOT_FOUND, str(exc))
            except json.JSONDecodeError:
                self._send_error(HTTPStatus.BAD_REQUEST, "Request body must be valid JSON")
            except ValueError as exc:
                self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            except Exception as exc:
                self._send_error(HTTPStatus.INTERNAL_SERVER_ERROR, str(exc))

        def _read_json(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length", "0"))
            if length == 0:
                return {}
            body = self.rfile.read(length).decode("utf-8")
            data = json.loads(body)
            if not isinstance(data, dict):
                raise ValueError("Request body must be a JSON object")
            return data

        def _send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
            data = json.dumps(payload, indent=2).encode("utf-8")
            self.send_response(status)
            self._send_common_headers("application/json; charset=utf-8", len(data))
            self.end_headers()
            self.wfile.write(data)

        def _send_error(self, status: HTTPStatus, message: str) -> None:
            self._send_json({"error": message}, status=status)

        def _send_common_headers(self, content_type: str, content_length: int) -> None:
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(content_length))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")

        def _send_static(self, parts: list[str]) -> None:
            if not parts:
                self._send_error(HTTPStatus.NOT_FOUND, "Not found")
                return
            candidate = (STATIC_DIR / Path(*parts)).resolve()
            if STATIC_DIR not in candidate.parents and candidate != STATIC_DIR:
                self._send_error(HTTPStatus.FORBIDDEN, "Forbidden")
                return
            self._send_file(candidate)

        def _send_file(self, path: Path) -> None:
            if not path.exists() or not path.is_file():
                self._send_error(HTTPStatus.NOT_FOUND, "Not found")
                return
            data = path.read_bytes()
            content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            self.send_response(HTTPStatus.OK)
            self._send_common_headers(content_type, len(data))
            self.end_headers()
            self.wfile.write(data)

        @staticmethod
        def _parts(path: str) -> list[str]:
            return [part for part in path.strip("/").split("/") if part]

        @staticmethod
        def _query_value(query: dict[str, list[str]], key: str) -> str | None:
            values = query.get(key)
            if not values:
                return None
            return values[0]

        def _required_query(self, query: dict[str, list[str]]) -> str:
            value = self._query_value(query, "q") or self._query_value(query, "query")
            if not value:
                raise ValueError("Query parameter q is required")
            return value

        def log_message(self, format: str, *args: Any) -> None:
            print(f"{self.address_string()} - {format % args}")

    return CompanyBrainHandler


def run(host: str, port: int, data_dir: str | Path) -> None:
    server = ThreadingHTTPServer((host, port), make_handler(data_dir))
    print(f"Company Brain running at http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Company Brain MVP server.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8000, type=int)
    parser.add_argument("--data-dir", default="data")
    args = parser.parse_args()
    run(args.host, args.port, args.data_dir)


if __name__ == "__main__":
    main()

# Company Brain MVP

This repository contains a runnable Company Brain MVP: executable company knowledge plus the organizational memory needed for agents to discover, reason about, and act on company operations.

The MVP is intentionally dependency-light. It uses Python's standard library for the API server and stores skills as pretty-printed JSON files with a `.skill.json` suffix. JSON is valid YAML 1.2, so these files can be moved to a YAML parser later without changing the shape of the skill schema.

## What Is Included

- Skills API for listing, fetching, executing, and learning from skills
- Decision engine with nested `all` / `any` / `not` conditions and common operators
- Ingestion service that turns raw operational notes into human-reviewable candidate skills
- Outcome learning that adjusts confidence scores and logs feedback
- Company Memory Graph with entities, relationships, evidence, and history
- Discovery engine that extracts process, steps, owners, exceptions, tools, and policies
- Temporal Brain snapshots for history-aware memory
- Conflict detection, confidence ranking, and resolution suggestions
- Graph query engine for owners, dependencies, affected systems, traces, and timelines
- Memory freshness scoring with staleness, expiry, confidence decay, and recommendations
- Organizational evolution records for what changed, why, who changed it, and likely impact
- Organizational simulator for "what breaks if X disappears?"
- Process mining over operational events
- Agent runtime for `goal -> plan -> execute -> learn`
- Coverage endpoint for skill confidence, domain coverage, and review backlog
- Static admin dashboard for skills, execution, review, ingestion, and coverage
- Seed skills for refunds, enterprise pricing exceptions, and supplier approval
- Unit tests for the decision engine, repository, candidate approval, and learning loop

## Architecture

```text
INGESTION
  raw Slack/wiki/ticket/meeting/source records
    ↓
DISCOVERY
  process, steps, owner, exceptions, policy, tool
    ↓
MEMORY GRAPH
  entities, relationships, evidence, temporal snapshots
    ↓
REASONING
  search, explain, trace, rank, detect conflicts, simulate org changes
    ↓
EXECUTION
  plan, execute skill-backed steps, record feedback
```

## Run Locally

```powershell
python -m company_brain.main --host 127.0.0.1 --port 8000
```

Then open:

```text
http://127.0.0.1:8000
```

On Windows, `python run_server.py --host 127.0.0.1 --port 8000` is an equivalent convenience command.

## API

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Health check |
| `GET` | `/brain/skills` | List skill summaries |
| `GET` | `/brain/skills/{skill_id}` | Fetch one skill definition |
| `POST` | `/brain/execute/{skill_id}` | Execute a skill with input context |
| `POST` | `/brain/learn` | Submit outcome feedback and update confidence |
| `POST` | `/brain/ingest` | Extract candidate skills from raw records |
| `GET` | `/brain/candidates` | List candidate skills awaiting review |
| `POST` | `/brain/candidates/{candidate_id}/approve` | Promote a candidate into an executable skill |
| `POST` | `/brain/candidates/{candidate_id}/reject` | Reject a candidate skill |
| `GET` | `/brain/coverage` | View coverage and confidence metrics |
| `GET` | `/brain/search?q=refund` | Search graph memory |
| `GET` | `/brain/graph` | Return entities, edges, and evidence |
| `GET` | `/brain/graph/explain?q=enterprise%20refund` | Explain a memory query with relationships and evidence |
| `GET` | `/brain/graph/neighbors/{entity_id}` | Return graph neighbors for an entity |
| `GET` | `/brain/graph/path?from=a&to=b` | Find a path between two entities |
| `GET` | `/brain/query/owner?q=refund%20policy` | Find accountable owners and approval owners |
| `GET` | `/brain/query/dependencies?q=refund%20process` | Find direct and transitive dependencies |
| `GET` | `/brain/query/affected?q=Zendesk` | Find systems affected by an entity changing or disappearing |
| `GET` | `/brain/query/trace?q=refund%20policy` | Trace a decision through owners, dependencies, relations, and evidence |
| `GET` | `/brain/query/timeline?entity_id=policy_refund_policy` | Return temporal history for an entity |
| `GET` | `/brain/discoveries` | Return structured discoveries extracted from source records |
| `GET` | `/brain/snapshots?entity_id=policy_refund_policy` | Return temporal memory snapshots |
| `GET` | `/brain/conflicts` | Detect policy/process conflicts across temporal memory |
| `GET` | `/brain/confidence/rankings` | Rank graph entities by confidence and evidence support |
| `GET` | `/brain/memory/health` | Return freshness, staleness, expiry, and decayed confidence |
| `GET` | `/brain/evolution?entity_id=policy_refund_policy` | Explain organizational memory evolution |
| `POST` | `/brain/events` | Store operational events for process mining |
| `GET` | `/brain/processes/flows` | Return discovered event transitions |
| `POST` | `/brain/plan` | Build an execution plan from graph memory |
| `POST` | `/brain/simulate` | Simulate removal of a person, team, tool, policy, or process |
| `POST` | `/brain/agent-tasks` | Run the agent runtime for a goal |

## Example Execution

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/brain/execute/refund_decision `
  -ContentType application/json `
  -Body '{"customer_tier":"enterprise","days_since_purchase":75,"previous_refund_requests":0,"churn_risk":false}'
```

## Example Memory Query

```powershell
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/brain/graph/explain?q=enterprise%20refund"
```

## Example Plan

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/brain/plan `
  -ContentType application/json `
  -Body '{"query":"refund process"}'
```

## Example Conflict Detection

```powershell
Invoke-RestMethod `
  -Uri http://127.0.0.1:8000/brain/conflicts
```

## Example Dependency Query

```powershell
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/brain/query/dependencies?q=refund%20process"
```

## Example Memory Health

```powershell
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/brain/memory/health?as_of=2026-06-01T00:00:00Z"
```

## Example Evolution

```powershell
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/brain/evolution?entity_id=policy_refund_policy"
```

## Example Simulator

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/brain/simulate `
  -ContentType application/json `
  -Body '{"query":"Zendesk"}'
```

## Example Agent Task

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/brain/agent-tasks `
  -ContentType application/json `
  -Body '{"goal":"enterprise refund","context":{"customer_tier":"enterprise"},"outcome":"success"}'
```

## Tests

```powershell
python -m unittest discover -s tests
```

## Next Production Steps

- Replace file storage with Postgres plus a graph store such as Neo4j
- Add real connectors for Slack, Zendesk, CRM, wiki, and procurement systems
- Put LLM extraction behind a review queue with source citations and redaction
- Add auth, RBAC, tenant isolation, audit logs, and encryption before ingesting real company data
- Publish Python and JavaScript SDKs for agent workflows

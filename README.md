# CompanyBrain

CompanyBrain is a first-customer-ready organizational memory runtime. It ingests source material, discovers entities and relationships, builds an evidence-backed memory graph, answers operational questions, and simulates what breaks when a person, tool, policy, or team changes.

The current goal is design-partner value, not enterprise procurement readiness. It is intentionally dependency-light and uses Python standard-library HTTP plus JSON file storage.

## What A First Customer Can Do

- Ingest real notes, SOPs, meeting summaries, tickets, or Notion pages
- Ask who owns a process
- See what depends on a tool
- Find policy conflicts and stale memory
- Identify tribal knowledge concentration across people and teams
- Explain every node, relation, process, and policy with source evidence
- Simulate scenarios such as a person leaving, a tool outage, or a policy change

## Core Flow

```text
INGESTION
  source records and connector syncs
DISCOVERY
  LLM-first schema extraction with deterministic fallback
MEMORY GRAPH
  entities, relationships, evidence, temporal snapshots
REASONING
  search, explain, trace, coverage, risk, conflict, simulation
EXECUTION
  plans, skill execution, agent tasks, feedback
```

## Run Locally

```powershell
python -m company_brain.main --host 127.0.0.1 --port 8000
```

Then open:

```text
http://127.0.0.1:8000
```

On Windows, this is also available:

```powershell
python run_server.py --host 127.0.0.1 --port 8000
```

## Optional LLM Discovery

The discovery pipeline uses an OpenAI-compatible chat completions endpoint when an API key is configured. Without a key it falls back to a deterministic schema extractor, so local tests and demos still work.

```powershell
$env:COMPANYBRAIN_LLM_API_KEY="..."
$env:COMPANYBRAIN_LLM_MODEL="gpt-4.1-mini"
$env:COMPANYBRAIN_LLM_ENDPOINT="https://api.openai.com/v1/chat/completions"
```

Every LLM discovery is normalized into:

- entities
- relationships
- processes
- policies
- evidence IDs
- confidence scores
- warnings when fallback extraction was used

## Notion Connector

Set a Notion token:

```powershell
$env:NOTION_API_KEY="secret_..."
```

Sync selected pages:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/brain/connectors/notion/sync `
  -ContentType application/json `
  -Body '{"page_ids":["your-page-id"]}'
```

For local testing or a concierge import, send exported records directly:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/brain/connectors/notion/sync `
  -ContentType application/json `
  -Body '{"records":[{"id":"page-1","title":"Refund SOP","content":"Enterprise refunds above $500 require finance approval. Handled in Zendesk."}]}'
```

Source sync status is available at:

```text
GET /brain/sources
```

## Product Screens

- Overview: risk score, real coverage state, confidence, bottlenecks, actions
- Knowledge Graph: entities, relation strength, filters, evidence, path explorer
- People & Teams: ownership, approvals, escalations, knowledge concentration
- Processes: owner, steps, tools, dependencies, policies, exceptions, evidence
- Coverage: documented processes, mapped policies, known owners, dependencies
- Gaps & Risks: missing owners, conflicts, stale memory, prioritized actions
- Simulation: scenario builder, comparison, mitigation testing, resilience score
- Evidence: source text, extracted insights, related entities and relationships
- Sources: connector status, sync time, documents processed, extracted knowledge
- Settings: Notion sync and manual source ingestion

## API Highlights

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/brain/dashboard` | Executive KPIs, health, gaps, actions |
| `GET` | `/brain/graph/view` | Graph nodes, edges, strength, evidence |
| `GET` | `/brain/processes` | Process explorer data |
| `GET` | `/brain/people` | People and teams explorer data |
| `GET` | `/brain/evidence` | Evidence explorer data |
| `GET` | `/brain/sources` | Connector and sync status |
| `GET` | `/brain/risks` | Risk center data |
| `GET` | `/brain/coverage/view` | Coverage drill-down |
| `GET` | `/brain/semantic-search?q=refund` | Evidence-aware graph search |
| `POST` | `/brain/connectors/notion/sync` | Notion initial or incremental sync |
| `POST` | `/brain/ingest` | Manual source record ingestion |
| `POST` | `/brain/simulation/run` | Scenario simulation and comparison |
| `POST` | `/brain/agent-tasks` | Goal to plan to execution runtime |

## Dashboard Integrity

The dashboard does not fabricate progress. If there is not enough temporal history to show a trend, the API returns:

```json
{
  "available": false,
  "message": "Insufficient historical data.",
  "points": []
}
```

The Knowledge Risk Score is derived from current graph confidence, stale or expired memory, unknown owners, and conflicts. Month-over-month deltas stay unavailable until real historical metrics exist.

## Tests

```powershell
python -m unittest discover -s tests
node --check company_brain\static\app.js
```

## Still Out Of Scope

- Multi-tenancy
- SSO and RBAC
- SOC2 and enterprise audit controls
- Kubernetes deployment
- Neo4j or Postgres migration
- Fully autonomous workers

Those are later-stage product hardening items. The present build is aimed at proving that a design partner can connect real knowledge and immediately get useful ownership, dependency, evidence, and simulation answers.

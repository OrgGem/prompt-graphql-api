# PromptQL MCP Server

Status: Unstable and only for PromptQL v1. Alpha release coming soon for PromptQL v2. 


## Overview

This project provides a bridge between Hasura's PromptQL data agent and AI assistants through the Model Context Protocol. With this integration, AI assistants can directly query your enterprise data using natural language, leveraging PromptQL's powerful capabilities for data access, analysis, and visualization.

## Features

- 🔍 **Natural Language Data Queries** - Ask questions about your enterprise data in plain English
- 📊 **Table Artifact Support** - Get formatted table results from your data queries
- 🔐 **Secure Configuration** - Safely store and manage your PromptQL API credentials
- 🔑 **Dual Authentication Modes** - Support for both public and private DDN deployments
- 📈 **Data Analysis** - Get insights and visualizations from your data
- 🛠️ **Simple Integration** - Works with Claude Desktop and other MCP-compatible clients

## Authentication Modes

The PromptQL MCP server supports two authentication modes to work with different DDN deployment types:

### Public Mode (Default)
- Uses `Auth-Token` header for authentication
- Compatible with public DDN endpoints
- Backward compatible with existing configurations
- **Use when**: Your DDN deployment is publicly accessible

### Private Mode
- Uses `x-hasura-ddn-token` header for authentication
- Compatible with private DDN endpoints
- Enhanced security for private deployments
- **Use when**: Your DDN deployment is private/internal

You can specify the authentication mode during configuration using the `--auth-mode` flag or `auth_mode` parameter.

## Installation

### Prerequisites

- Python 3.10 or higher
- A Hasura PromptQL project with API key, playground URL, and DDN Auth Token
- Claude Desktop (for interactive use) or any MCP-compatible client

### Install from Source

1. Clone the repository:
```bash
git clone https://github.com/hasura/promptql-mcp.git
cd promptql-mcp
```

2. Set up a virtual environment (recommended):
```bash
# Create a virtual environment
python -m venv venv

# Activate the virtual environment
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install the package:
```bash
pip install -e .
```

## Quick Start

1. Configure your PromptQL credentials:

```bash
# For public DDN deployments (default)
python -m promptql_mcp_server setup --api-key YOUR_PROMPTQL_API_KEY --playground-url YOUR_PLAYGROUND_URL --auth-token YOUR_AUTH_TOKEN --auth-mode public

# For private DDN deployments
python -m promptql_mcp_server setup --api-key YOUR_PROMPTQL_API_KEY --playground-url YOUR_PLAYGROUND_URL --auth-token YOUR_AUTH_TOKEN --auth-mode private
```

**Alternative: Environment Variables**
```bash
export PROMPTQL_API_KEY="your-api-key"
export PROMPTQL_PLAYGROUND_URL="your-playground-url"
export PROMPTQL_AUTH_TOKEN="your-auth-token"
export PROMPTQL_AUTH_MODE="public"  # or "private"
export PROMPTQL_HASURA_GRAPHQL_ENDPOINT="http://localhost:8080/v1/graphql"  # optional for query_hasura_ce
export PROMPTQL_HASURA_ADMIN_SECRET="your-hasura-admin-secret"                # optional
```

2. Test the server:

```bash
python -m promptql_mcp_server
```

3. In a new terminal, try the example client:

```bash
python examples/simple_client.py
```

## Using with Claude Desktop

1. Install [Claude Desktop](https://claude.ai/download)
2. Open Claude Desktop and go to Settings > Developer
3. Click "Edit Config" and add the following:

```json
{
  "mcpServers": {
    "promptql": {
      "command": "/full/path/to/python",
      "args": ["-m", "promptql_mcp_server"]
    }
  }
}
```

Replace `/full/path/to/python` with the actual path to your Python executable.

If you're using a virtual environment (recommended):
```json
{
  "mcpServers": {
    "promptql": {
      "command": "/path/to/your/project/venv/bin/python",
      "args": ["-m", "promptql_mcp_server"]
    }
  }
}
```

**Alternative: Using Environment Variables in Claude Desktop**
```json
{
  "mcpServers": {
    "promptql": {
      "command": "/full/path/to/python",
      "args": ["-m", "promptql_mcp_server"],
      "env": {
        "PROMPTQL_API_KEY": "your-api-key",
        "PROMPTQL_PLAYGROUND_URL": "your-playground-url",
        "PROMPTQL_AUTH_TOKEN": "your-auth-token",
        "PROMPTQL_AUTH_MODE": "public"
      }
    }
  }
}
```

To find your Python path, run:
```bash
which python  # On macOS/Linux
where python  # On Windows
```

4. Restart Claude Desktop
5. Chat with Claude and use natural language to query your data

### Example Prompts for Claude

- "What were our total sales last quarter?"
- "Who are our top five customers by revenue?"
- "Show me the trend of new user signups over the past 6 months"
- "Which products have the highest profit margin?"

## Available Tools and Prompts

### Tools
The server exposes the following MCP tools:

### Thread Management Mode
- **start_thread** - Start a new conversation thread with an initial message and wait for completion (returns thread_id, interaction_id, and response)
- **start_thread_without_polling** - Start a new conversation thread without waiting for completion (returns thread_id and interaction_id immediately)
- **continue_thread** - Continue an existing thread with a new message (maintains conversation context)
- **get_thread_status** - Check the status of a thread (processing/complete) using GET /threads/v2/{thread_id}
- **cancel_thread** - Cancel the processing of the latest interaction in a thread

### Configuration
- **setup_config** - Configure PromptQL API key, playground URL, DDN Auth Token, and authentication mode (public/private)
- **check_config** - Verify the current configuration status including authentication mode
- **query_hasura_ce** - Prompt-driven query flow for Hasura CE v2 (metadata -> planner -> GraphQL -> synthesized answer)

## Usage Examples

### Multi-Turn Conversation Mode

#### Option 1: Start with polling (get immediate response)
```python
# Start a new conversation thread (waits for completion and returns full response)
thread_result = await client.call_tool("start_thread", {
    "message": "What tables are available in my database?"
})

# Extract thread_id from result (format: "Thread ID: abc-123\nInteraction ID: def-456\n\n[response content]")
thread_id = thread_result.split("Thread ID: ")[1].split("\n")[0].strip()

# Continue the conversation with context
result = await client.call_tool("continue_thread", {
    "thread_id": thread_id,
    "message": "Show me the schema of the users table"
})
```

#### Option 2: Start without polling (check status separately)
```python
# Start a new conversation thread (returns immediately with thread_id)
thread_result = await client.call_tool("start_thread_without_polling", {
    "message": "What tables are available in my database?"
})

# Extract thread_id from result (format: "Thread ID: abc-123\nInteraction ID: def-456\n\n...")
thread_id = thread_result.split("Thread ID: ")[1].split("\n")[0].strip()

# Check status manually
status_result = await client.call_tool("get_thread_status", {
    "thread_id": thread_id
})

# Continue when ready
result = await client.call_tool("continue_thread", {
    "thread_id": thread_id,
    "message": "Show me the schema of the users table"
})

# Continue further
result = await client.call_tool("continue_thread", {
    "thread_id": thread_id,
    "message": "How many records are in that table?"
})

# Check thread status
status = await client.call_tool("get_thread_status", {
    "thread_id": thread_id
})

# Cancel thread processing (if currently processing)
cancel_result = await client.call_tool("cancel_thread", {
    "thread_id": thread_id
})
```

### With System Instructions
```python
# Start thread with system instructions
result = await client.call_tool("start_thread", {
    "message": "Show me the top 10 products by revenue",
    "system_instructions": "Format all results as markdown tables"
})
```

## Configuration Examples

### Setting Up Authentication Modes

#### Public Mode Configuration (Default)
```python
# Using MCP tool
result = await client.call_tool("setup_config", {
    "api_key": "your-api-key",
    "playground_url": "https://promptql.your-domain.public-ddn.hasura.app/playground",
    "auth_token": "your-auth-token",
    "auth_mode": "public"
})
```

#### Private Mode Configuration
```python
# Using MCP tool
result = await client.call_tool("setup_config", {
    "api_key": "your-api-key",
    "playground_url": "https://promptql.your-domain.private-ddn.hasura.app/playground",
    "auth_token": "your-auth-token",
    "auth_mode": "private"
})
```

#### Checking Current Configuration
```python
# Check what authentication mode is currently configured
config_result = await client.call_tool("check_config", {})
# Returns configuration details including auth_mode
```

### Prompts
- **data_analysis** - Create a specialized prompt for data analysis on a specific topic

## Architecture

This integration follows a client-server architecture:

1. **PromptQL MCP Server** - A Python server that exposes PromptQL capabilities through the MCP protocol
2. **MCP Client** - Any client that implements the MCP protocol (e.g., Claude Desktop)
3. **PromptQL API** - Hasura's Natural Language API for data access and analysis

The server translates between the MCP protocol and PromptQL's API, allowing seamless integration between AI assistants and your enterprise data.

### Backend Architecture Blueprint: Prompt Query API + Hasura Metadata

For a backend API service that receives prompt queries (search/Q&A), uses an LLM to decide GraphQL queries based on metadata, then post-processes and returns final answers, use the following architecture:

1. **API Gateway / BFF Layer**
   - Exposes REST endpoints (e.g., `POST /v1/query`, `POST /v1/query/stream`)
   - Handles authentication, rate limiting, request validation, and tracing IDs
2. **Prompt Orchestrator Service**
   - Classifies intent (lookup, aggregation, comparison, explain)
   - Coordinates metadata retrieval, query planning, execution, and answer synthesis
   - Applies policy checks before any generated query is executed
3. **Metadata Service (Hasura-first)**
   - Reads Hasura metadata (models, relationships, permissions, naming, docs)
   - Builds a normalized schema context for LLM consumption
   - Caches metadata snapshots and refreshes on schedule/webhook
4. **LLM Query Planner**
   - Converts user prompt + schema context into a constrained query plan:
     - target entities/fields
     - filters/sort/limit
     - confidence and fallback strategy
   - Produces structured output (JSON) instead of raw GraphQL text when possible
5. **GraphQL Builder + Guardrails**
   - Translates structured plan into GraphQL
   - Enforces allowlist/denylist, max depth, max row limit, timeout budget
   - Prevents disallowed operations (sensitive fields, broad scans)
6. **Hasura GraphQL Execution Layer**
   - Executes GraphQL against Hasura (single source for DB connectivity and RBAC)
   - Reuses Hasura permissions to keep data access centralized
7. **LLM Response Synthesizer**
   - Converts raw query results into natural-language answer
   - Supports output modes: concise answer, markdown table, JSON payload
   - Adds provenance (queried entities, filters, timestamp)
8. **Observability + Safety**
   - Structured logs (prompt hash, chosen entities, latency stages)
   - Metrics (token usage, query latency, cache hit rate, error classes)
   - Optional human-review or fallback templates for low-confidence answers

Recommended request flow:

`Client -> API Gateway -> Prompt Orchestrator -> Metadata Service (cache) -> LLM Query Planner -> GraphQL Builder/Guardrails -> Hasura -> LLM Response Synthesizer -> Client`

### Hasura CE v2.x Compatibility Notes (Important)

If your source-of-truth data layer is **Hasura CE v2.x (latest)**, keep the following constraints in scope during implementation:

- Use Hasura v2 capabilities as the execution backbone:
  - GraphQL query/mutation/subscription over tracked sources
  - Hasura metadata APIs for schema models, relationships, permissions, and naming
  - Role-based access control enforced at Hasura layer
- Do **not** assume PromptQL/NL features are provided by Hasura CE v2 itself.
  - Natural-language understanding, query planning, and answer synthesis remain application-layer responsibilities (LLM services in your backend).
- Plan around CE v2 operational boundaries:
  - no dependence on DDN-only managed features
  - no dependence on metadata semantics that exist only in newer product lines
  - enforce guardrails (depth/row/time limits) in your own backend before sending GraphQL to Hasura

Practical implementation guidance for CE v2:

1. Treat Hasura metadata as schema context input to LLM (not as an NL query engine).
2. Keep an adapter layer that maps normalized metadata -> planner context -> GraphQL builder.
3. Validate every generated query against CE-safe rules before execution.
4. Keep fallback templates for unsupported/ambiguous prompts instead of issuing unsafe broad queries.

#### Phase-by-phase CE v2 Compatibility Checklist

- **Phase 1: Foundation (CE-safe scope)**
  - API contracts only expose capabilities backed by CE v2 GraphQL + metadata.
  - Error model distinguishes:
    - unsupported by CE v2
    - unsupported by current app implementation
- **Phase 2: Metadata Context Pipeline**
  - Metadata fetcher reads only CE v2 metadata endpoints and tracked-source schema.
  - Normalizer does not depend on DDN-specific metadata semantics.
- **Phase 3: LLM Query Planning**
  - Planner output schema is constrained to CE-executable query patterns.
  - Any planned operation outside CE-safe policy is rejected before GraphQL generation.
- **Phase 4: Query Guardrails + Execution**
  - GraphQL builder only emits CE v2-compatible queries for tracked entities/relationships.
  - Guardrails enforce depth/rows/timeout and block broad scans.
- **Phase 5: Answer Synthesis**
  - Response synthesis uses only fields returned by CE v2 execution (no hidden enrichments).
  - Unsupported prompt intents return deterministic fallback responses.
- **Phase 6: Quality & Security**
  - Add compatibility tests for planner outputs that must be rejected under CE constraints.
  - Add regression tests for role/permission behavior as enforced by Hasura CE v2 RBAC.
- **Phase 7: Production Readiness**
  - Release checklist explicitly verifies no DDN-only feature flags or assumptions are enabled.
  - Monitoring includes CE-compatibility error classes for fast detection of scope drift.

### Detailed Development Plan (Draft)

- **Phase 1: Foundation**
  - Define API contracts (`/v1/query`, `/v1/query/stream`, `/v1/schema/context`)
  - Add auth, request validation, correlation IDs, error envelope format
  - Set up logging/metrics/tracing baseline
- **Phase 2: Metadata Context Pipeline**
  - Implement Hasura metadata fetcher + normalizer
  - Add cache (TTL + manual refresh) and versioning
  - Create schema summarization for token-efficient LLM prompts
- **Phase 3: LLM Query Planning**
  - Design planner prompt template and JSON schema output
  - Implement intent detection and plan validation
  - Add retry strategy for invalid/ambiguous plans
- **Phase 4: Query Guardrails + Execution**
  - Build GraphQL generator from planner JSON
  - Enforce limits (depth, cost, timeout, max rows, field restrictions)
  - Execute via Hasura and standardize error mapping
- **Phase 5: Answer Synthesis**
  - Build response templates (Q&A, table, summary, compare)
  - Add citation/provenance block and confidence score
  - Support multilingual answers and deterministic formatting options
- **Phase 6: Quality & Security**
  - Add golden tests for prompt -> plan -> query -> answer pipeline
  - Add adversarial tests (prompt injection, over-broad query attempts)
  - Add PII masking/redaction in logs and strict secret handling
- **Phase 7: Production Readiness**
  - Add SLOs, autoscaling strategy, circuit breakers, and graceful degradation
  - Add cost controls (token budgets, caching, configurable model tiers)
  - Roll out progressively with canary traffic and feedback loop
  - Maintain a CE v2 compatibility checklist to prevent accidental adoption of non-CE features

## Troubleshooting

### Command not found: pip or python
On many systems, especially macOS, you may need to use `python3` and `pip3` instead of `python` and `pip`.

### externally-managed-environment error
Modern Python installations often prevent global package installation. Use a virtual environment as described in the installation section.

### No module named promptql_mcp_server
Ensure you've:
1. Installed the package with `pip install -e .`
2. Are using the correct Python environment (if using a virtual environment, make sure it's activated)
3. Configured Claude Desktop to use the correct Python executable path

### Python version issues
If you have multiple Python versions installed, make sure you're using Python 3.10 or higher:
```bash
python3.10 -m venv venv  # Specify the exact version
```

### Authentication Issues

#### Wrong authentication mode
If you're getting authentication errors, verify you're using the correct authentication mode:

- **Public DDN deployments**: Use `--auth-mode public` (default)
- **Private DDN deployments**: Use `--auth-mode private`

Check your current configuration:
```bash
python -m promptql_mcp_server
# Then use check_config tool to see current auth_mode
```

#### Switching authentication modes
To switch between authentication modes, simply reconfigure:
```bash
# Switch to private mode
python -m promptql_mcp_server setup --api-key YOUR_API_KEY --playground-url YOUR_URL --auth-token YOUR_TOKEN --auth-mode private

# Switch back to public mode
python -m promptql_mcp_server setup --api-key YOUR_API_KEY --playground-url YOUR_URL --auth-token YOUR_TOKEN --auth-mode public
```

## Development

### Project Structure

```
promptql-mcp/
├── promptql_mcp_server/     # Main package
│   ├── __init__.py
│   ├── __main__.py          # Entry point
│   ├── server.py            # MCP server implementation
│   ├── config.py            # Configuration management
│   └── api/                 # API clients
│       ├── __init__.py
│       └── promptql_client.py # PromptQL API client
├── examples/                # Example clients
│   └── simple_client.py     # Simple MCP client
├── setup.py                 # Package configuration
└── README.md                # Documentation
```

### Mockup Test with Hasura CE v2 + Test DB Container

To validate the CE-v2 flow (metadata -> planner -> GraphQL -> answer synthesis), run:

```bash
cp tests/mockup/.env.example tests/mockup/.env  # optional, to customize ports/secrets
chmod +x tests/mockup/run_hasura_mockup_tests.sh
tests/mockup/run_hasura_mockup_tests.sh
```

This starts:
- Postgres test DB (seeded with `customers` table)
- Hasura CE v2 container
- integration test: `tests/test_hasura_ce_container_mockup.py`

### DevOps Review: Scope Fit vs Plan and Docker Readiness

Current implementation status against the phased plan:

- ✅ Phase 2/3/4 baseline path exists: metadata export, simple planner, GraphQL execution, synthesized answer.
- ✅ CE v2 compatibility is respected (no DDN-only dependency in the new `query_hasura_ce` flow).
- ✅ Mockup integration test proves end-to-end local execution with Hasura CE + Postgres.
- ⚠️ Planner is currently minimal (keyword-to-table + count aggregate). Advanced intent handling from later phases (see **Detailed Development Plan** above) is not implemented yet.
- ⚠️ Guardrails are basic (`max_limit` clamp). Depth/cost policy and stricter allowlist are still roadmap items.

Docker env readiness for mockup stack:

- Required for startup (with defaults provided in compose):
  - `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_PORT`
  - `HASURA_PORT`, `HASURA_GRAPHQL_ADMIN_SECRET`
- Optional tuning:
  - `HASURA_GRAPHQL_ENABLE_CONSOLE`, `HASURA_GRAPHQL_DEV_MODE`, `HASURA_GRAPHQL_ENABLED_LOG_TYPES`
  - `HASURA_GRAPHQL_DATABASE_URL` (override auto default)
- Source of truth template: `tests/mockup/.env.example`

### Next DevOps Plan: Build Complete Image(s)

1. **App image**
   - Build `promptql-mcp-server` image (python slim, non-root user, healthcheck).
   - Inject runtime config via env vars (no secrets baked into image).
2. **Optional sample Hasura profile**
   - Keep app-only compose as default.
   - Add optional profile/service for Hasura + Postgres sample stack.
3. **Release & CI**
   - Multi-stage build, pinned base tag, dependency cache.
   - CI pipeline for lint/test + image build + vulnerability scan.
   - Tagging strategy: `vX.Y.Z`, `sha-<short>`, and `latest` (optional).

### DevOps Implementation (Container + Compose)

The repository now includes:
- `Dockerfile` for `promptql-mcp-server` runtime image
- `.dockerignore` for lean image builds
- `docker-compose.yml`:
  - `promptql-mcp` service (default)
  - optional `sample-hasura` profile with `postgres` + `hasura`
- `.env.devops.example` template for compose variables

Build and run app container:

```bash
cp .env.devops.example .env  # optional
docker compose build promptql-mcp
docker compose up promptql-mcp
```

Run app + sample Hasura CE stack:

```bash
cp .env.devops.example .env
# set POSTGRES_PASSWORD and HASURA_GRAPHQL_ADMIN_SECRET in .env before first run
docker compose --profile sample-hasura up --build
```

Note: The sample Hasura stack is for local/dev testing only. Do not use default credentials in non-local environments.

### Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgements

- [Hasura](https://hasura.io/) for creating PromptQL
- [Anthropic](https://www.anthropic.com/) for developing the Model Context Protocol


## TODO
- process the thread response properly based on interaction_id returned as part of continue_thread and start_thread in mcp_server, at the moment, it only looks for the latest interaction_id
- process the interaction_response accordingly to figure out the code, plan and code_output
- ensure the simple_client.py shows the cancellation_thread demo properly, the current status call looks to be blocking 
- Validate if the artifacts are processed accordingly

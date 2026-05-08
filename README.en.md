<p align="right"><a href="./README.md"> 中文</a> | English</p>

<p align="center">
  <img src="./assets/logo.png" width="360" alt="OpenAaaS Logo">
</p>

<p align="center"><strong>OpenAaaS — Open Us to the Agentic World</strong></p>

<p align="center">
  <a href="https://www.open-aaas.com">Website</a> ·
  <a href="./server/README.md">Server Docs</a> ·
  <a href="./agent-core/README.md">Agent Core Docs</a> ·
  <a href="#Usage">Usage Guide</a> ·
  <a href="./client-extension/README.md">Client Extensions</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Rust-1.85%2B-orange?logo=rust" alt="Rust">
  <img src="https://img.shields.io/badge/License-MIT-blue.svg" alt="License">
  <img src="https://img.shields.io/badge/tests-590%2B-brightgreen" alt="Tests">
</p>

---

**Code flows, data stays still — bring AI to the data, instead of handing data over to AI.**

**OpenAaaS is building an Agentic capability network for scientific research.**

The bottleneck of AI has shifted from model capability to the accessibility of scientific capabilities, while "data being forced to move" is a harder constraint than models. Every lab has accumulated unique data, algorithms, and workflows, but they are scattered in silos and cannot be discovered or invoked. OpenAaaS distributes Agent capabilities to data nodes locally, enabling any Agent to discover, invoke, and compose capabilities from scientific nodes around the world — data is processed in place, while code and instructions flow through the network.

Any Agent — whether Claude Code, pi mono, Kimi Cli, or a self-built system — can discover and compose capabilities from scientific nodes across the network through the web.

At the same time, we strive to minimize the barrier to using the network, even for general-purpose LLM apps on mobile phones.

| Demo Video | Screenshots |
|:---:|:---:|
| <video src="https://github.com/user-attachments/assets/196ae678-e9e7-4c3f-9160-57a3aa7d040b"></video> | **Connect Service**<img width="372" height="113" alt="Screenshot 2026-05-07 09 36 25" src="https://github.com/user-attachments/assets/d3773d67-9d47-45db-9f5e-3ca96f990981" /><br>**View Service List**<img width="379" height="406" alt="Screenshot 2026-05-07 09 37 22" src="https://github.com/user-attachments/assets/d74571ac-b300-411e-9371-b51822531926" /><br>**Service Result Returned**<img width="371" height="391" alt="Screenshot 2026-05-07 09 38 09" src="https://github.com/user-attachments/assets/16c9984b-e730-476c-93e7-1aae78f76a5d" /> |

## Core Design Philosophy

Traditional cloud solutions require data to leave the premises: TB-scale datasets must be uploaded, sensitive samples are handed to third parties, and lab firewalls are forced to open inbound ports. OpenAaaS takes the opposite approach — deploying Agent execution nodes directly where the data resides. The network only transmits task descriptions, task files, and results; raw data is processed on-site.

| | Traditional Cloud Solution | OpenAaaS Near-Data Solution |
|---|---|---|
| Data Flow | Local → Cloud → Local | **Raw data stays in place** |
| Network Transfer | Raw data (TB scale) | Task descriptions, task files, and results (KB–MB scale) |
| Firewall Requirements | Inbound ports required | **Outbound HTTP only** |
| Sensitive Data | Must leave the domain | **Never leaves the lab** |
| Latency | Bandwidth-limited | Local compute, extremely low latency |

## Architecture

```
Client Agent
(pi mono / Claude Code / Kimi Cli / Cline / Custom Agent)
        ▲
        │ Control flow: task description, heartbeat, results (KB scale)
        ▼
───────────────────────────────────────────────────────────────────
OpenAaaS Server (Network Hub)
Rust + SQLite — Lightweight indexing layer
  • Service registration  • Task routing  • Node heartbeat  • File relay
        ▲
        │ Short polling (unidirectional outbound HTTP)
        ▼
───────────────────────────────────────────────────────────────────
Agent Core (Network Node)
Rust + Docker — Deployed locally where data resides
  • Register capabilities to the network  • Poll for tasks
  • Container sandbox isolation execution  • Report results
        │              │                   │
        ▼              ▼                   ▼
   [Local Dataset]  [Analysis Scripts]  [Specialized Hardware]
    (TB scale)      (Algorithms/Models)  (GPU/Instruments)
```

| Layer | Component | Responsibility |
|------|------|------|
| Client Agent | pi mono / Kimi Cli / Codex / Open Code / Custom Agent | Understand tasks, discover network nodes, schedule remote capabilities, integrate results |
| Network Hub | Server — Capability registration and scheduling center (Rust + SQLite) | Service registration, task routing, node heartbeat, file relay |
| Network Node | agent-core — Capability execution node + Docker | Register capabilities to the network, poll for tasks, execute in sandbox isolation, report results |

## Design Rationale

| Principle | Description | Effect |
|------|------|------|
| Rust + Single Binary | `cargo build --release` produces one executable | Zero-dependency deployment, copy and run |
| Embedded SQLite | Database starts with the process, no separate service | Zero operations, single node is sufficient |
| Docker Isolation | Each task runs in an independent container with workspace mounted | Secure and controllable, reproducible environment |
| Self-Organizing Nodes | Nodes actively register with the network and poll for tasks; Server only maintains an index. Raw data never leaves the domain; task files flow through the Server | Nodes need no public IP; unidirectional outbound is enough to join the network; data is processed on-site, naturally adapting to lab firewall environments |

## Features

- **🔒 Data Never Leaves the Premises** — Agent execution nodes are deployed directly on lab servers or instrument workstations. Raw large datasets are processed in-place via local mounts; sensitive data never crosses the firewall. The network only transmits task descriptions, task files, and results; it never touches raw data.

- **🔧 Zero-Config Node Onboarding** — `open-aaas-server run` auto-generates `config.toml`, SQLite database, and keys on first launch. No manual configuration; ready to use out of the box.

- **🐳 Independent Sandbox per Experiment, Reproducible Results** — Each task runs in an isolated container with workspace mounts for input and output. Environment isolation makes results traceable and reproducible.

- **💾 Single Binary, Zero Operations** — SQLite database + local file storage; no Redis/MySQL required. A single node is enough for deployment, ideal for lab edge nodes.

- **🔌 Zero-Learning-Cost Agent Integration, Self-Describing API Auto-Exposes Service Docs** — No authentication required; returns complete API documentation and usage instructions. Agents can understand and invoke all scientific services without any plugins.

- **⚖️ Nodes Join via Reverse Connection, No Public IP Needed** — Nodes self-manage concurrency and task claiming; Server only does lightweight queue management. Lab nodes only need unidirectional outbound access to join; no open ports or SSH required.

- **🧩 Progressive Capability Discovery, Avoiding Context Overflow** — Initial queries return lightweight summaries; detailed usage is returned on demand. A progressive disclosure design similar to SKILL.md protects the Agent's context window.

- **🤖 MCP Standard Protocol Compatible** — Through `openaaas-mcp-adapter`, any MCP-compatible client such as Claude Desktop, Cursor, or Cline can connect with one click, without writing any plugins.

## Usage

Public Server: **<https://api.open-aaas.com>**

We provide three trial scientific services on the public server:

- IDM-Alpha Metal Materials Literature Research Assistant
- Hexa-High-Entropy Alloy Descriptor Database
- Fuyao Multi-Expert Discussion System

You can have your Agent connect to the public server to use them.

### Quick Start

**Scenario 1: Use the Public Server**

No need to build your own infrastructure. Simply configure your Agent to connect to the public server and start invoking community-shared scientific services. Ideal for individual researchers to get started quickly.

### Using the pi / Kimi Plugin

Just say in the conversation:

> "Help me set the OpenAaaS server address to <https://api.open-aaas.com>, then submit a data analysis task"

The client Agent will automatically complete registration, service discovery, task submission, and result retrieval.

### Using an MCP Client (Claude Desktop / Cursor / Cline)

If you are using **OpenClaw** or any other Agent that supports MCP (Model Context Protocol), connecting to the OpenAaaS network is nearly zero-cost — no plugins to write, just one configuration entry to invoke all capabilities.

```json
{
  "mcpServers": {
    "openaaas": {
      "command": "uvx",
      "args": ["openaaas-mcp-adapter"]
    }
  }
}
```

After configuring, restart the client, and you can invoke OpenAaaS's 14 standard Tools (`set_server_url`, `register`, `list_services`, `submit_task`, etc.) directly in conversation without installing any plugins.

See [client-extension/openaaas-mcp-adapter/README.md](./client-extension/openaaas-mcp-adapter/README.md) for details.

### Using a General Agent Framework

If your Agent does not have an OpenAaaS plugin, simply have it access <https://api.open-aaas.com>:

- No authentication required; complete API documentation and usage instructions are returned
- The Agent can then automatically complete registration, service discovery, and task submission after reading them

**Scenario 2: Deploy on a Lab Server and Connect Local Capabilities**

Launch OpenAaaS on a local server in your machine room or lab, and register local analysis scripts and specialized computing workflows as network nodes. Any Agent in the research group — pi, Kimi, Claude, or a self-built system — can query node status, submit analysis tasks, and retrieve result data through a unified entry point.

### Local Deployment

**Deploy Server (Scheduling Center)**:

```bash
cd server
cargo build --release
./target/release/open-aaas-server run
```

On first launch, `config.toml` and the SQLite database are auto-generated.

**Deploy Agent Core (Execution Node)**:

```bash
cd agent-core
cargo build --release
./target/release/agent-core init
./target/release/agent-core register --token <registration_token> --name my-agent
./target/release/agent-core run
```

The `registration_token` must be obtained by creating a Service on the Server first. Admins can use the API Key from the Server logs to call `POST /api/v1/services/` to create one.

The Agent executor image needs to be built in advance (under the agent-core directory):

```bash
cd executor-example && docker build -t open-aaas-executor:latest .
```

See [agent-core/README.md](./agent-core/README.md) for details.

## Project Structure

```
OpenAaaS/
├── server/           # Network Hub (Scheduling Center) (Rust) — Task scheduling, queuing, auth, file relay
├── agent-core/       # Network Node (Execution Node) (Rust) — Registration, polling, Docker-isolated execution
├── dash/             # Debug and admin tools (Python/Streamlit)
└── client-extension/ # Client extensions — pi plugin, Kimi plugin, MCP adapter (Claude Desktop / Cursor / Cline)
```

## Research Vision

OpenAaaS's vision is to make every lab a composable node in the Agentic Science network. Each research group has accumulated unique analysis workflows, datasets, and computational methods — these capabilities are no longer trapped within a single team, but become standard units on the network that any Agent can discover, invoke, and orchestrate. When scientific capabilities move from silos to the network, the boundary of innovation will expand from the closed loop of a single lab to an open ecosystem of global collaboration.

## Open Source License

MIT License © IDM Explorer Lab

<img src="./assets/idm-logo.png" width="200" alt="IDM Explorer Lab">

# Scaling LangGraph, LlamaIndex, and CrewAI, Part 1: State and Recovery

*By [Alexander Chernov](https://www.linkedin.com/in/thedoytsujin/). First published on LinkedIn, 2026-11-06. [Read the original](https://www.linkedin.com/pulse/scaling-langgraph-llamaindex-crewai-part-1-state-recovery-chernov-msshc/).*

---

*Part 1 of two on scaling agent frameworks. This part is state and recovery. Part 2 is load, inference, and authorization.*

LangGraph, LlamaIndex, and CrewAI are application orchestration frameworks. They define what an agent workflow does, and they do not supply the distributed system that runs it. When a worker dies in the middle of a step, the effect of that step can happen twice. In a crash test of all three frameworks, a worker was killed after a payment and before the framework recorded the step. Without a stable idempotency key, the resumed run charged twice every time. With a key derived from the run and the step, and saved in the framework's state before the payment, it charged once every time.

The frameworks' own documentation draws the same line: LangGraph's says a retry "does not make external side effects happen exactly once," and LlamaIndex's says "Resume is at-least-once." Adding graph replicas is the easy part. The harder work is scaling state, tool execution, inference, isolation, and governance. The working principle is to separate five concerns: workflow orchestration, distributed execution, persistent state, inference serving, and policy enforcement.

Every framework capability below is stated as its vendor documents it, read on 2026-11-05. The measured results come from the crash test, described below, and from my published work, each named where it appears.

## Three planes

An agent platform divides into three planes:

- **Control plane:** what an agent is permitted to do and under which conditions. It holds graph definitions and versions, agent and tool registration, policy evaluation, tenant identity and authorization, execution budgets, deployment configuration, human approval requirements, and audit configuration.
- **Execution plane:** the work itself. It schedules graph steps, dispatches asynchronous jobs, runs MCP tools, invokes models, runs isolated code, manages retries and timeouts, enforces resource limits, and scales each workload independently.
- **State plane:** execution context and recovery. It preserves session state, graph checkpoints, task status, idempotency records, tool execution receipts, persistent memory, artifact references, and audit history.

A request crosses them in order: client → API gateway (authentication, quotas) → agent orchestration (the framework) → durable execution (queues, leases, checkpoints) → Kubernetes worker pools (graph, tool, sandbox).

The workers then reach three shared services: a state store (PostgreSQL, S3, Redis), a policy plane (OPA or Cedar, approvals), and an LLM gateway (LiteLLM, vLLM, external APIs). OpenTelemetry metrics, traces, and audit records span all of it. This separation keeps the framework from becoming one service that is hard to scale, secure, and operate.

## What each framework is for

These are architectural differences, not performance rankings.

**LangGraph** is stateful graph orchestration, built from nodes, edges, interrupts, and checkpoints. It suits workflows that need explicit transitions, durable execution, human approval, and conditional branching: retrieve context → evaluate policy → reason → approve or suspend → execute → checkpoint → finalize. Its documentation recommends a persistent checkpointer for production and labels SQLite as a development option. It offers three durability modes, from `exit` to `sync`, and `sync` writes every checkpoint before the next step starts. The LangSmith Agent Server adds a deployment tier in which API servers persist runs and queue workers execute them. The principal concern is state consistency and graph coordination.

**LlamaIndex** is strongest on data: document ingestion, SQL and knowledge-graph retrieval, vector search, metadata filtering, and evidence-grounded synthesis. Its workflows are event-driven steps that can branch and run concurrently under a `num_workers` cap. Durability is more explicit than in LangGraph. The documentation says "There is no built-in checkpointer to enable": the application snapshots the context at step boundaries, or a DBOS runtime journals step transitions to a database. `SqliteWorkflowStore` is the simple option for one process, and with Postgres "multiple server replicas can share the same database for distributed execution and recovery." The principal concern is retrieval and ingestion fan-out.

**CrewAI** is collaboration among specialized agents. For example, a planner hands work to a researcher and a developer, and a reviewer checks the result. Its documentation recommends wrapping crews in a Flow, and `@persist` saves Flow state. The default backend is a local SQLite database, so replicas in separate pods share nothing until a shared backend is supplied through the `FlowPersistence` interface. For infrastructure, the documentation points to CrewAI Enterprise. The Flows and production architecture pages describe no queue or worker tier, so on an open deployment that tier belongs to the surrounding platform.

CrewAI documents two ways back from a failure. Resuming a `@persist` Flow hydrates the saved state and runs the Flow again from its first method. Checkpointing, a separate feature, saves execution state each time a method finishes, and a Flow restored from a checkpoint skips the methods already completed.

Roles are worth their cost only when they measurably improve task quality. Multi-agent execution adds model calls, context propagation, chances for inconsistent decisions, coordination latency, harder debugging, and potentially unbounded interaction loops. A deterministic sequence of operations usually needs a conventional workflow rather than a team of autonomous agents.

![A crash and a resume as objects on one white tabletop. A steel track runs through three glass stations: prepare, charge, finalize. A worker module with its light out sits after the payment terminal: worker killed after the charge. A second worker with its light on sits before the terminal: a new worker resumes from the saved state. Behind the stations, a card-index cabinet with an open drawer: saved state, the charge is not yet recorded. A brass tag hangs from that drawer: a stable key, saved before the charge. One receipt lies in the terminal's tray: same key, so the service charges once.](scaling-agent-frameworks/article_figure.webp)

## Durable execution and idempotency

Take the workflow retrieve → reason → approve → execute → finalize. Suppose the external operation succeeds and the process crashes before the checkpoint is written. On resume the operation may run again. For a read-only tool that is harmless. For a payment, a deployment, a data modification, or an infrastructure operation it can be dangerous.

The frameworks document this behavior directly. LangGraph writes checkpoints at super-step boundaries, not mid-function, and its documentation says: "Side effects during the node (payments, emails, external writes) are outside that boundary. Application code must make those effects idempotent." LlamaIndex says: "A step that was mid-execution when you captured the state is rewound and runs again from the top." CrewAI's Checkpointing page says that on restore "Completed tasks are skipped," so a method that was interrupted runs again.

A crash test measures that gap. The workflow prepare → charge → finalize ran on one machine in LangGraph 1.2.16 with its SQLite checkpointer, in LlamaIndex Workflows 2.26.1 with the documented snapshot loop, and in CrewAI 1.15.28 with `@persist` and with Checkpointing. A separate payments service counted every charge.

Each worker was killed with SIGKILL at one point and then resumed, five times for each setup, key, and kill point, 180 trials in all.

Killed after the charge and before the framework recorded the step, every setup charged twice, in all 39 trials without a stable key. A key generated inside the step made no difference, because the replay generates a new one. A key derived from the run and the step, and saved in the framework's state before the step, gave one charge in all 19 trials. Killed before the charge, every setup charged once.

Killed after the record, three of the four setups charged once. CrewAI's `@persist` charged twice in all 10 trials without a stable key, because its resume runs the Flow again from the first method. The stable key was the only protection that held in every setup and at every kill point.

Three of the 45 resumes under CrewAI Checkpointing stopped with an exception inside CrewAI's checkpoint writer: "dictionary changed size during iteration." The Checkpointing page describes automatic checkpoint writes as best-effort, with a failed write logged and the run continuing. Those three trials are left out of the counts above.

"Exactly-once" needs a careful reading. The LangSmith scalability page says each attempt for each run is handled by a single instance, "with exactly-once semantics enforced through Postgres's MVCC model." The same page describes a sweeper that runs every 2 minutes and returns runs that breached their heartbeat window to the queue.

So the guarantee covers who holds an attempt. It does not cover how many times an external effect happened.

A realistic design starts from at-least-once delivery with idempotent or reconciled effects. A broker may deliver a task twice, a worker may act and crash before acknowledging, and an engine may replay a started step. Exactly-once effects need guarantees from the external system, transactional integration, or a reconciliation protocol.

Each side-effecting step therefore needs a durable execution record: `run_id`, `step_id`, `attempt_id`, `idempotency_key`, `tenant_id`, `graph_version`, `execution_status`, `lease_owner`, `lease_expiration`, `fencing_token`, and `result_reference`. A task moves through PENDING → CLAIMED → EXECUTING → SUCCEEDED, FAILED, or UNKNOWN. UNKNOWN means reconciliation is required. LangGraph's documentation states the rule: "Treat missing local state as unknown, not as proof the effect did not happen."

The design needs seven mechanisms:

1. Stable idempotency keys for logically identical operations, durable before the effect runs.
2. Durable task records.
3. Worker leases and fencing tokens.
4. Transactional outbox patterns where appropriate.
5. Retries with exponential backoff and jitter.
6. Dead-letter handling or terminal failure states.
7. Reconciliation for uncertain external outcomes.

Agentic Delivery shows the idempotency key at work. In its run of 2026-10-21 against a local k3s cluster, a refund whose response was lost was retried under the same call id and produced one decision, executed once. The call ledger reconciled one to one with the service's own log.

![Charges the payments service recorded after a worker was killed and the run resumed, five trials per tile, in four setups: LangGraph with its SQLite checkpointer, LlamaIndex Workflows with the documented snapshot loop, and CrewAI with @persist and with Checkpointing. Killed before the charge: one charge in every setup. Killed after the charge and before the framework recorded the step: two charges without a key and with a key made inside the step, one charge with a stable key, in every setup. Killed after the record: one charge, except CrewAI @persist without a stable key, which charged twice. Three CrewAI Checkpointing resumes stopped with an exception inside CrewAI and are left out.](scaling-agent-frameworks/fig_crash.webp)

## Externalize sessions and state

Conversation state should not be tied to a pod. A useful hierarchy is tenant → user → conversation → run, and each run carries its graph version, checkpoint id, pending tasks, tool receipts, and policy context. Any eligible executor should be able to resume from a durable checkpoint, provided concurrent execution is controlled.

An agent requesting approval for a production deployment shows the difference. The system persists the current state, records the pending approval, releases execution resources, and notifies the authorized reviewer. When a valid decision arrives, it resumes, revalidates policy and execution preconditions, and continues under appropriate authorization. The original worker pod does not need to remain alive.

Each store has one responsibility:

- **PostgreSQL:** authoritative workflow and execution state.
- **Redis:** ephemeral cache, coordination, or rate limiting.
- **pgvector:** semantic memory and similarity retrieval.
- **S3-compatible storage:** large artifacts, documents, and outputs.
- **Kafka or NATS JetStream:** durable asynchronous messaging.
- **Dedicated audit storage:** execution evidence and retention.

Graph checkpoints should not carry entire documents or binary payloads. They should hold immutable artifact references and the relevant metadata.

Persistent memory is not execution state. Execution state records what is happening in an active or suspended workflow, while semantic memory holds reusable information learned or retrieved across interactions. Vector search should not become the authority on transaction status. PostgreSQL records whether an operation succeeded, pgvector may help retrieve related prior incidents, object storage holds the resulting artifact, and the audit ledger records why the operation was authorized.

![The square poster for this article: the same track with three glass stations for prepare, charge and finalize, a card-index cabinet whose open drawer holds a brass tag, and one receipt in the terminal's tray, above the title and the line: A key saved before the step. One charge after a crash.](scaling-agent-frameworks/poster_square.webp)

## Workflow versioning for long-running agents

An execution starts on Monday and suspends for approval. A new graph version deploys on Tuesday. The user approves on Wednesday. The question is whether the new application can safely resume the old checkpoint.

Renamed nodes, changed state schemas, modified tool contracts, different prompt structures, new authorization requirements, removed paths, and changed model output formats can each break it. LangGraph's documentation is specific about two of these. For an interrupted thread, a missing node name fails the run on resume, so a node the thread is about to enter must not be renamed or removed. Renaming a state key drops the saved value for that key in existing threads.

Every execution should persist `run_id`, `graph_id`, `graph_version`, `state_schema_version`, `policy_version`, and `checkpoint_id`. The platform then needs explicit rules for resuming on the original graph version, migrating compatible state, rejecting incompatible migrations, revalidating authorization, and retaining older executors during transition. For long-running regulated workflows, versioning is a correctness and governance concern.

## Sources

- LangChain, "Fault tolerance," LangGraph documentation. <https://docs.langchain.com/oss/python/langgraph/fault-tolerance>
- LangChain, "Functional API overview," LangGraph documentation. <https://docs.langchain.com/oss/python/langgraph/functional-api>
- LangChain, "Graph API overview," LangGraph documentation. <https://docs.langchain.com/oss/python/langgraph/graph-api>
- LangChain, "Checkpointers," LangGraph documentation. <https://docs.langchain.com/oss/python/langgraph/checkpointers>
- LangChain, "Persistence," LangGraph documentation. <https://docs.langchain.com/oss/python/langgraph/persistence>
- LangChain, "Scalability and resilience," LangSmith documentation. <https://docs.langchain.com/langsmith/scalability-and-resilience>
- LangChain, "Configure LangSmith Agent Server for scale." <https://docs.langchain.com/langsmith/agent-server-scale>
- LlamaIndex, "Writing durable workflows." <https://developers.llamaindex.ai/python/llamaagents/workflows/durable_workflows/>
- LlamaIndex, "Run Your Workflow as a Server." <https://developers.llamaindex.ai/python/llamaagents/workflows/deployment/>
- CrewAI, "Flows." <https://docs.crewai.com/en/concepts/flows>
- CrewAI, "Production Architecture." <https://docs.crewai.com/en/concepts/production-architecture>
- CrewAI, "Checkpointing." <https://docs.crewai.com/en/concepts/checkpointing>
- A. Chernov, "Agents Propose, a Gate Decides: Governed Delivery for Agent-Written Software," 2026. <https://www.linkedin.com/pulse/agents-propose-gate-decides-governed-delivery-software-chernov-fi9cc/>

Every link above was checked on 2026-11-05, and the CrewAI Checkpointing page again on 2026-11-06.

#AgenticAI #AIAgents #LangGraph #LlamaIndex #CrewAI #DistributedSystems #PlatformEngineering #LLMOps

---

<small>© 2026 Alexander Chernov. All rights reserved. First published on [LinkedIn](https://www.linkedin.com/pulse/scaling-langgraph-llamaindex-crewai-part-1-state-recovery-chernov-msshc/), which remains the canonical version; this page is a reprint by the author.</small>

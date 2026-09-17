# Implementation plan: local bank knowledge assistant

## 1. Purpose and delivery contract

Implement the proof of concept described in `README.md`. This plan is for the in-house coding agent, which has access to the actual documents, internal services, and deployment environment. The assistant being built answers questions; it is not a coding agent and must not execute arbitrary code or modify source systems.

Deliver a German-language conversational CLI, backed by reusable application services that can later be exposed through FastAPI. Implement sources sequentially: general rules, website, intranet, historical contract decisions, then private document folders. After the final source, complete cross-source reviews and rule-by-rule assessment.

Use this document as the recommended baseline, not as evidence about unavailable infrastructure. Verify source schemas, model capabilities, and installed versions before implementing integrations. Record deviations and their measured rationale in short architecture decision records. Do not silently change the requirements in the README.

### Fixed requirements

- All source access is read-only. Derived text, metadata, indexes, and logs may be written locally.
- No external runtime services, model APIs, telemetry, or automatic asset downloads. Internal bank services are permitted.
- Use Python >= 3.11, uv, pytest, Pydantic AI, Docling where appropriate, existing MySQL and Weaviate, and the specified models served through local vLLM endpoints.
- Deploy on SLES 15 using Podman and Quadlets. Verify the installed systemd/Podman versions support the planned units.
- Use dummy identities and roles for the CLI. Restrict each shared source by role and each private collection by owner.
- Refresh shared sources daily; ingest private files when they are added or explicitly refreshed. Leave original files untouched.
- Keep conversation state in memory. Support follow-up questions and new retrieval when necessary.
- Answers require precise supporting source citations. Explain contradictions or insufficient evidence and ask how to proceed.
- Start with general books when consulting rules. Product-only questions need not consult rules.
- Historical decisions explain past cases; the POC does not approve or deny new cases.
- Sensitive passages and answers may be included in local POC debugging logs. Production requires a stricter policy.

### Explicitly deferred

JIRA, Confluence, SharePoint, production SSO, a web UI, persistent conversations, document/section-level shared-source permissions, high availability, and automated business decisions are outside this POC. Keep interfaces suitable for these extensions without implementing them prematurely.

## 2. Discovery before implementation

Create `docs/discovery.md` and a redacted configuration example. Inspect representative real data; do not copy sensitive examples into the repository.

The user will provide the vLLM endpoint details. Configure chat, embedding, and reranker clients independently through typed settings loaded from environment variables or a local configuration file: base URL, served model ID, optional authentication secret, request timeout, and any required endpoint path. Allow the clients to share a base URL or use separate endpoints. Keep secrets out of committed examples. Validate required settings at startup and use the `doctor` command to test connectivity and model capabilities. Provisioning or configuring the vLLM servers is outside the implementation scope.

| Area | Establish and record | Result required before proceeding |
| --- | --- | --- |
| Rule books | Storage/API, document IDs, general/specific hierarchy, chapter boundaries, cross-references, applicability, current/draft status | Explicit book hierarchy and a representative conversion sample |
| Website | SOLR query schema, exact identifier filters, full content retrieval, stable URLs, pagination and export capabilities | Working read-only query and passage retrieval |
| Intranet | REST authentication, pagination, content formats, search support, deletion detection | Reliable enumeration and retrieval strategy |
| Decisions | Case/contract identifiers, multiple decisions per case, dates, reason fields, attachments | Unambiguous exact-case lookup rules |
| Private folders | Configured user-to-folder mapping, formats, file sizes, supported refresh behavior | Owner-isolated ingestion of a sample folder |
| Document quality | German scans, OCR needs, tables, headings, duplicate versions, available source locators | Conversion failure and citation-quality report |
| Models | Exact served IDs/revisions, context lengths, tokenizer, embedding dimensions and query/document prefixes, German support, reranker endpoint and length limits | Successful chat, embedding, reranking, and structured-output smoke checks |
| Infrastructure | Internal endpoints, TLS trust, credentials, CPU/RAM/GPU capacity, disk space, MySQL/Weaviate versions and access rights | Supported deployment and connectivity matrix |
| Dependencies | Existing lockfile, required slim-package extras, internal artifact availability, licenses | Reproducible environment without runtime downloads |
| Evaluation | Golden JSON shape, stable document/passage references, reviewers and representative question categories | Versioned evaluation dataset and rubric |

Do not assume the informal model names in the README identify exact downloadable checkpoints. In particular, verify tool calling and structured output against the actual chat model and vLLM configuration. If tool calling is unreliable, retain Pydantic AI for validated model calls and use application-controlled routing/retrieval; do not depend on an unbounded autonomous tool loop.

Determine which records are authoritative/current using source metadata or an owner-maintained mapping. If that information is unavailable, expose the uncertainty rather than inferring authority from retrieval scores or filenames.

## 3. Architecture

Use one application-level assistant with a small set of typed retrieval tools and deterministic workflow services. A separate agent per source adds coordination complexity without a demonstrated need at this scale.

```text
CLI + configured dummy identity
          |
Conversation / question-answering / review services
          |
Authorization + authorized source catalog
          |
Retrieval orchestration ---- Pydantic AI ---- local vLLM chat
          |                         |
          |                  validated answer + citations
          |
Source adapters / exact lookup / hierarchy navigation
          |
MySQL normalized evidence + metadata     Weaviate search indexes
          ^                                      ^
          |                                      |
Read-only connectors -> conversion -> chunking -> local embeddings
                                   -> staged ingestion and publication

Local reranker refines retrieved candidates before evidence selection.
```

Keep these boundaries separate:

- **Connectors** enumerate and fetch original content with provenance. They do not decide answer wording.
- **Ingestion** normalizes content, preserves locators, generates chunks/embeddings, and publishes validated generations.
- **Retrieval** applies mandatory authorization and generation filters, searches, reranks, and expands context.
- **Application workflows** control scope confirmation, rule enumeration, budgets, conversation state, and failure handling.
- **Model integration** performs bounded classification, query formulation, evidence interpretation, and answer drafting.
- **Presentation** renders German text and citations or JSON without embedding business logic in the CLI.

Recommended package layout, adapted to the existing `pydanticai_poc` package:

```text
src/pydanticai_poc/
  cli.py
  config.py
  domain/          # Pydantic contracts, identities, evidence, answers
  auth/            # source and owner authorization
  connectors/      # rules, SOLR, REST, decisions, local folders
  ingestion/       # normalization, Docling, chunking, generations
  storage/         # MySQL repositories and Weaviate adapter
  retrieval/       # exact, lexical, dense, hybrid, rerank, hierarchy
  models/          # local chat, embedding, reranker clients
  workflows/       # conversation, QA, comparison, rule assessment
  evaluation/      # golden-set adapter, metrics, reports
tests/
  unit/
  integration/
  acceptance/
config/
deploy/
docs/
```

Use dependency injection for the authenticated identity, source registry, repositories, model clients, and request budget. Pydantic AI supports typed dependencies and message history; bind these to application-owned state rather than accepting identity supplied in a model tool call. Consult the available `building-pydantic-ai-agents` skill and its local `references/AGENTS-CORE.md` and `references/INPUT-AND-HISTORY.md` files for these patterns. Reference paths here are relative to the named skill directory, wherever it is installed.

## 4. Retrieval recommendations

RAG means retrieving evidence and then generating an answer from it. It does not require a vector database: an exact case lookup or SOLR query followed by a grounded answer is also retrieval-augmented generation. Some tasks need deterministic lookup or complete enumeration rather than similarity search.

| Source | Recommended baseline | Why this approach | Alternatives to measure |
| --- | --- | --- | --- |
| General rules, ~8,000 documents | Hierarchy-aware hybrid retrieval, local reranking, parent-section expansion, explicit general-to-specific traversal | Exact rule terms and section references benefit from keyword matching; German paraphrases benefit from semantic matching; hierarchy preserves qualifications and inherited rules | Keyword-only, dense-only, hybrid without reranker; compare structure-aware chunks with a simple fixed-size baseline |
| Website, ~8,000 documents | Existing SOLR keyword retrieval plus full product-section fetch; exact lookup for named products | Reuses available search and preserves product names, identifiers, and authoritative links; avoids duplicating an index before demonstrating benefit | Add a local Weaviate semantic index only if paraphrase recall is insufficient; fuse result ranks rather than raw SOLR/vector scores |
| Intranet, ~2,000 documents | Daily REST ingestion into a local hybrid index, filtered by department/topic where useful | REST retrieval alone may not provide search; metadata and hybrid search cover names as well as conceptual questions | Native REST search if discovery finds it adequate; keyword-only baseline |
| Historical decisions, ~1,000 documents | Exact authorized case/contract lookup first, then fetch decision and supporting reasons/attachments | Similar cases cannot establish why a particular case was decided; explicit identifiers and dates prevent case mixing | Hybrid search for discovery when no ID is supplied; ask the user to disambiguate before explaining a specific case |
| Private folders, ~100 documents/user | Owner-filtered hybrid search, with exact selected-document fetch and bounded full-document reading | Supports questions across a collection while enabling detailed review of one document; access isolation is mandatory | Whole-document context for small files; lexical baseline for exact terms |

Weaviate combines keyword and vector retrieval in hybrid search and supports query filters. Keep authorization filters in every query regardless of retrieval mode. Consult the available `weaviate` skill's local `references/hybrid_search.md` and `references/fetch_filter.md`, and the `weaviate-cookbooks` skill's `references/basic_rag.md` and `references/advanced_rag.md` for retrieval and filtered-query examples.

Adapt these skills to the requirements in this plan: use the existing internal Weaviate instance, application-supplied embeddings from the local Snowflake model, and application-side reranking through the local Qwen endpoint. Supply the locally generated query vector for semantic/hybrid retrieval and configure derived collections for self-provided vectors using the installed client's supported API. Do not copy the skills' cloud connection defaults, hosted vectorizers, external rerankers, Query Agent services, or DSPy framework choice. Retain Pydantic AI. Optional model-generated topic filters must be combined with mandatory application-owned authorization and generation filters; they cannot replace or weaken them. The sample hybrid-search CLI does not expose these mandatory filters, so use an application adapter rather than exposing that script directly as an assistant tool. For client lifecycle and internal connection patterns, consult `weaviate-cookbooks/references/async_client.md` relative to the skills root, checking examples against the installed client version.

### Candidate retrieval and evidence selection

1. Honor an explicit source/document selection after checking authorization; otherwise select from the authorized source catalog.
2. Resolve exact identifiers first. Preserve original identifiers during query rewriting.
3. For rules, retrieve relevant general-book sections before following explicit links or applicability mappings to specific books. Log this traversal. Do not make one successful general-book search a substitute for establishing the applicable scope.
4. Start experiments with 40 candidates per relevant source, rerank approximately 20, and select roughly 6–10 passages for ordinary QA. These are tunable starting values, not acceptance criteria.
5. Deduplicate overlapping passages, retain source diversity when the question spans sources, and expand parent/adjacent sections to preserve definitions, exceptions, tables, and qualifications.
6. Respect the actual model context budget, reserving room for instructions, conversation, and output. Use bounded staged reading for large sections rather than silently truncating evidence.
7. Run one bounded recovery retrieval using alternative terms or referenced sections when evidence is inadequate. Ask the user if the remaining gap needs clarification.

Do not interpret retrieval or reranker scores as probabilities of correctness. Do not compare uncalibrated scores across different sources. If results must be merged, use rank fusion or a shared reranking stage and validate it on cross-source questions.

Do not initially implement GraphRAG, fine-tuning, synthetic-answer retrieval, or recursive multi-agent research. Consider graph-style retrieval only if measured failures require relationships beyond the explicit book/chapter/reference hierarchy. Consider fine-tuning only for demonstrated behavioral needs; it does not replace current, attributable evidence.

## 5. Data contracts and citation provenance

Define versioned Pydantic contracts and database migrations before integrating sources.

| Contract | Required information |
| --- | --- |
| `UserContext` | Stable dummy user ID, roles, session ID; immutable within a session |
| `SourceDefinition` | Source ID/type, required role or owner, connector configuration reference, refresh policy, supported operations |
| `Document` | Source/document IDs, owner if private, title, original locator, content hash, source version/date if known, ingestion generation, hierarchy/applicability metadata |
| `Passage` | Stable locator within a document version, exact normalized text, book/chapter/section path, page if available, offsets/block IDs, parent/reference IDs |
| `SearchHit` | Passage reference, retrieval method/rank, optional diagnostic score, generation |
| `Evidence` | Validated authorized passage, citation locator, version, exact supporting text |
| `Answer` | Status, German answer, evidence-linked claims, citations, contradictions, missing evidence, clarification question |
| `Assessment` | Confirmed scope, enumerated requirements, evidence on both sides, per-rule status, unresolved items, coverage counts |

Store manifests, active-generation pointers, normalized evidence, hierarchy, and provenance in MySQL. Store retrieval text, vectors, passage references, generation, source, and owner/filter metadata in Weaviate. Treat MySQL evidence records as the authoritative source for resolving citations; generated summaries are navigation aids only.

Use structured columns for frequently filtered fields and JSON only for source-specific metadata. Select suitable text/blob storage after measuring document sizes; use local managed files for large converted artifacts if necessary. Store credentials separately from source definitions.

Citation rendering must use retrieved metadata, never model-invented URLs or page numbers. A citation identifies document title, source, section/chapter/page where available, document version/hash, and an original link or local locator. For HTML, use a heading/anchor and an excerpt locator; do not invent a page number. Retain a mapping from normalized chunks to original blocks so chunking does not destroy provenance.

Before display, validate that each citation resolves to evidence actually retrieved for the current authorized request. Check quoted text against that evidence. Semantic support requires evaluation in addition to identifier validation; a valid citation ID does not prove that a claim follows from the passage.

## 6. Ingestion and safe replacement

### Conversion and chunking

- Prefer native structured text from SOLR/REST when it preserves headings and locators. Use Docling for PDFs, office files, scans, and other supported formats where conversion adds value.
- Preserve headings, lists, table captions/headers, references, and exceptions. Inspect representative German/OCR samples manually before bulk ingestion.
- Start with structure-aware chunks around 400–800 embedding-model tokens, adjusting to the actual model limits. Split long sections without losing their parent path. Preserve small tables as units; split large ones with repeated headers and provenance.
- Record parser, chunker, tokenizer, model revision, dimensions, and configuration hashes. Changed embedding dimensions or chunking logic require a new compatible index generation.
- Keep model assets and OCR dependencies local. Do not enable runtime download fallbacks.

Docling supports structure-aware chunking; verify the extracted hierarchy rather than assuming headings were detected correctly. Consult the available `docling` skill's local `references/python-sdk.md` sections on chunking for RAG, inspecting document structure, and recovering heading levels, plus `references/rag.md` for direct chunker usage.

### Publication protocol

1. Acquire a per-source ingestion lock and create an inactive generation ID.
2. Enumerate the complete source with pagination and deletion detection. An incomplete listing is an ingestion failure, not evidence that missing documents were deleted.
3. Fetch, normalize, chunk, and embed into staging records. Reuse unchanged artifacts by content/configuration hash, while ensuring the staged generation is logically complete.
4. Validate expected document counts, conversion coverage, duplicate IDs, citation resolution, vector dimensions, and index query visibility. Report failed documents; do not silently publish a partial replacement.
5. Mark staging ready only after both MySQL evidence and Weaviate retrieval records pass validation.
6. Atomically update the source's active-generation pointer in MySQL. This is the publication boundary; there is no assumed transaction spanning MySQL and Weaviate.
7. Each answer pins a generation per source at request start, and all retrieval/fetch operations use those generations. Retain old generations only while active requests need them, then delete obsolete derived records and artifacts.
8. On any pre-publication failure, leave the previous generation active, clean failed staging data, and report stale-source status. On restart, reconcile incomplete generations and interrupted cleanup.

Keep synchronization full and correct before optimizing incremental ingestion. Historical decision records remain present while they exist in the authoritative source; “old data” means obsolete derived copies, not old case dates. Removing a file from a private folder removes its indexed copy on the next successful folder refresh; ingestion never deletes the original file.

At a new conversation turn, use current active generations. Prior answers may remain in memory, but superseded passages must not serve as current evidence: re-fetch them or mark them unavailable. Clear session evidence on identity changes.

## 7. Authorization and model boundaries

Implement a central policy service. `everyone` permits the website, `internal` permits rules/intranet, `department_a` permits decisions, and owner identity permits private collections. Do not assume role inheritance unless configured explicitly; an internal department user can hold both roles.

Expose only authorized source descriptions to the model. Enforce authorization again in every retrieval and direct-fetch operation, including exact IDs, parent expansion, reference traversal, citations, assessment enumeration, and caches. For private folders, use a logical source per owner or equivalent mandatory owner filter. Source-level shared permissions do not remove the need for private owner isolation.

Identity and authorization filters come from application dependencies, never from user prose or model arguments. Cache keys must include user/permission scope, generation, query, and retrieval configuration. Keep conversations isolated by user and session.

The dummy CLI identity mechanism is a local POC fixture, not real authentication. Keep it behind an identity-provider interface for later SSO integration. Do not expose a service where callers can freely choose roles.

Treat document text as untrusted evidence. Distinguish business instructions being analyzed (for example, a bank rule) from instructions trying to control the assistant. Source text must not alter tools, permissions, prompts, or network destinations. Do not expose shell execution, unrestricted filesystem access, arbitrary SQL, arbitrary URLs, or source-writing tools to the assistant. Resolve document links through configured connectors and apply authorization again.

## 8. Question answering and conversations

Proposed typed operations, with identity bound outside model-visible parameters:

- `search_source(source_id, query, filters)`
- `fetch_passages(source_id, document_id, locators)`
- `navigate_rules(book_id, section_id)`
- `lookup_decision(case_id, decision_date=None)`

The application validates all IDs and filters and applies request budgets. It may hide unavailable tools or use one retrieval facade; neither approach replaces server-side checks.

For each turn:

1. Resolve pronouns and references against in-memory conversation state; preserve explicit document/source choices.
2. Classify the task as lookup, ordinary QA, cross-source comparison, or rule assessment.
3. Retrieve fresh authorized evidence when the question changes, evidence is insufficient, or the active generation changed.
4. Draft a German answer tied to evidence IDs. Separate source facts from conclusions inferred by comparing passages.
5. Validate the structured output and citations with bounded retries. If validation fails, report inability to provide a grounded answer rather than outputting unchecked text.
6. Render the answer, source citations, contradictions, and any specific clarification question. Track status such as `answered`, `partial`, `needs_clarification`, or `insufficient_evidence`.

Model knowledge may help formulate queries and explain the workflow, but must not fill missing bank facts or rules. When evidence is missing, state what is missing and ask how to proceed. When sources conflict, cite both positions and ask for relevant context or scope; user preference alone must not be presented as establishing which rule is authoritative.

Limit retrieval rounds, tool calls, retries, output tokens, and total duration through configuration. A limit reached mid-task produces an explicit incomplete result. Summarized conversation history can preserve user intent and references, but is not a replacement for source evidence. Maintain the tool-message structure required by the installed Pydantic AI version.

## 9. Cross-source comparison and exhaustive rule assessment

### Cross-source comparison

Decompose the question into evidence needs: for example, retrieve the selected product description from the website and the applicable wording guidance from the intranet. Preserve source roles rather than merging passages into an undifferentiated context. Report each comparison with evidence from both sides. Missing guidance or an unavailable source yields an unresolved item, not a positive compliance conclusion.

### Rule-by-rule workflow

This is a separate workflow from top-k question answering:

1. Identify the target document and candidate applicable books/chapters, starting with general rules and following explicit specializations and references.
2. Present the proposed scope for user confirmation. Users may supply the scope directly; record that selection. Clarify ambiguous or incomplete selections.
3. Enumerate every section in the confirmed scope deterministically from the stored hierarchy. Follow relevant referenced requirements and flag references outside the agreed scope for clarification.
4. Extract individual requirements with exact supporting passages and applicability conditions. Preserve a section-to-requirement coverage map, including sections judged non-normative and extraction failures. Validate this extraction against human-annotated samples.
5. For each requirement, search and, where necessary, read the relevant target-document sections. Use bounded batches to cover long documents. Searching only a few similar chunks is not proof that evidence is absent.
6. Produce one result per requirement: `met`, `not_met`, `not_applicable`, or `insufficient_evidence`. Cite the rule and target evidence. Use `not_met` for supported contradictions or verified missing mandatory content after adequate review; otherwise use `insufficient_evidence`.
7. Validate that every enumerated requirement has a result. Show section and requirement counts, unsupported applicability decisions, unreadable content, unfinished batches, and unresolved references.
8. Summarize only within the confirmed scope. Never claim that every possible bank requirement was checked. Even complete section enumeration does not establish perfect requirement extraction; report extraction limitations.

Store workflow state in memory for the POC, including scope confirmation and completed batches. If the process exits, explain that the assessment must restart; durable review jobs belong to a later phase.

## 10. Evaluation and acceptance

Build evaluation alongside the first source. Golden data is provided as JSON with question, answer, and sources, usually including specific passages. Adapt that input to a canonical format rather than requiring contributors to guess implementation chunk IDs.

Recommended optional fields: case ID, task type, user roles/owner, document version, passage locator or quoted span, expected answer status, required claims, and rule-level expected outcomes. Pin an evaluation corpus snapshot; flag stale golden references after refresh rather than counting them as unexplained retrieval failures.

Use a development set for tuning and a held-out set for reporting. Include German paraphrases, exact IDs, tables, OCR, general/specific exceptions, conflicting sources, missing evidence, unauthorized sources, private-user isolation, follow-ups, and multi-source questions. Report sample sizes and metrics separately by source and task.

### Metrics

| Layer | Measure |
| --- | --- |
| Ingestion | Document/section coverage, conversion failures, resolvable locators, freshness, refresh duration |
| Retrieval | Passage Recall@20/40, first-relevant rank/MRR, nDCG where graded labels exist, relevant-evidence coverage after reranking |
| Grounding | Citation validity, citation support precision, proportion of factual claims with supporting citations |
| Answers | Human-rated factual correctness and required-claim completeness; correct abstention and contradiction handling |
| Assessment | Section enumeration coverage, requirement extraction recall, per-rule agreement, unresolved-item reporting |
| Authorization | Unauthorized source/owner leakage, including metadata, citations, history, and cached evidence |
| Performance | End-to-end p50/p95 latency, stage latency, tokens, tool calls, model errors, and resource consumption |

Match gold passages using stable source locators or span overlap, not exact chunk boundaries. When only document-level gold exists, report document-level metrics separately; do not call them passage recall. Support alternative valid passages to avoid penalizing equivalent evidence.

Initial experimental targets, to refine after measurements: passage Recall@40 >= 0.90, citation support precision >= 0.95, and >= 0.90 human-rated correctness on answerable ordinary QA. These are proposed goals, not established performance or production assurances. Set task-specific latency targets after measuring actual hardware.

Hard functional gates: no observed unauthorized disclosure in the acceptance suite; all emitted citation IDs resolve to authorized evidence; failed ingestion preserves the previous active generation; every enumerated assessment requirement receives a result or is explicitly incomplete; unresolved/missing evidence must not produce a fabricated definitive answer. Passing finite tests does not establish absence of all possible leaks or reasoning errors.

Compare keyword, dense, hybrid, and hybrid-plus-reranker on the same snapshot. Change one major variable at a time. Evaluate chunking, candidate count, parent expansion, and German query formulation before adding architectural complexity. Local LLM judging can help triage, but domain reviewers own correctness judgments, especially for rule assessments.

## 11. Implementation stages

### Stage 0 — Discovery and reproducible foundation

Complete discovery, verify model endpoints, inspect the existing package, preserve its entry point, pin compatible dependencies using uv, and add typed configuration. Confirm slim-package extras and Docling/OCR assets. Provide dummy identities, local fixtures, migrations, and a connectivity diagnostic.

**Exit:** the project installs from the approved environment, tests run, and all required local model/database calls work. Unknown capabilities have documented decisions or explicit blockers.

### Stage 1 — General rules end to end

Implement source enumeration, hierarchy mapping, conversion, provenance, staged publication, authorization, and keyword baseline retrieval. Then add hybrid retrieval, reranking, hierarchy traversal, German grounded answers, and in-memory follow-ups. Build the first golden-set evaluation report.

**Exit:** an internal user can ask and follow up with passage citations; a public-only user cannot discover rule content; general-to-specific traversal is visible in diagnostics; failed refresh and malformed model-output tests pass. Record measured retrieval choices before adding the next source.

### Stage 2 — Website

Implement read-only SOLR search and product fetching. Persist a daily normalized snapshot where feasible to stabilize citations. If SOLR must be queried live, explicitly record that freshness model and verify fetched content versions rather than pretending it uses the local generation protocol. Add product routing without rule lookup. Benchmark semantic augmentation only if needed.

**Exit:** product queries work for public and internal users, exact product identifiers are preserved, citations resolve, and existing rule tests do not regress.

### Stage 3 — Intranet

Implement REST ingestion, metadata-aware hybrid retrieval, source-specific evaluation, and the first website-versus-intranet comparison workflow.

**Exit:** department/topic questions and product wording comparisons cite the correct sources; public users cannot access intranet content.

### Stage 4 — Historical contract decisions

Implement exact case lookup, dated decision selection, reason/attachment fetching, ambiguity questions, and department-role enforcement. Add discovery search only where needed.

**Exit:** explanations use the selected historical case, never a similar case's reasons; multiple decisions are distinguished; unauthorized users cannot retrieve case metadata.

### Stage 5 — Private folders

Implement owner-bound folder ingestion on the CLI upload/import operation, hashes for changed files, full-document fetch, and folder refresh. Restrict file resolution to the configured folder and handle symlinks explicitly to prevent crossing owner boundaries.

**Exit:** two dummy users cannot access each other's files through search, direct IDs, citations, or follow-ups; original files remain after ingestion; deleted-file refresh removes only the derived copy.

### Stage 6 — Rule assessments and complete evaluation

Implement scope confirmation, deterministic section enumeration, requirement extraction, per-rule assessment, coverage reports, and large-document batching. Complete multi-source and failure-case evaluations with domain reviewers.

**Exit:** confirmed-scope assessments show every requirement and unresolved item; interruption and missing-evidence cases cannot appear complete. Deliver comparative retrieval results and recommendations based on actual measurements.

### Stage 7 — Deployment and handover

Package the CLI and ingestion runner, supply deployment units and runbooks, validate on SLES 15, and document the future FastAPI adapter. Use the existing MySQL/Weaviate installations rather than provisioning replacements.

**Exit:** a clean environment can install/start the POC, perform daily refreshes, run a conversation, reproduce an evaluation report, and recover from failed ingestion using the runbook.

## 12. Tests, CLI, and operations

### Tests to implement

- Unit tests for authorization decisions, locator mapping, generation selection, scope/coverage logic, configuration validation, and output/citation validation.
- Connector contract tests for pagination, exact IDs, malformed responses, deleted records, incomplete listings, and stable provenance.
- Integration tests against isolated MySQL/Weaviate test data for generation publication, request pinning, cleanup/restart behavior, and owner/source filters across every retrieval mode.
- Workflow tests with deterministic model doubles for contradictions, follow-ups, context limits, malformed outputs, timeouts, and prompt-injection text.
- Opt-in local-model acceptance tests and golden evaluations; keep model-quality variability separate from deterministic pytest assertions.
- A network-isolated runtime smoke test showing models/OCR assets are available locally and no external fallback is required.

Never run destructive tests against existing shared production collections or databases. Give test resources their own namespace and cleanup policy.

### Proposed CLI commands

These are commands to implement, not commands already available:

```text
uv run pydanticai-poc doctor
uv run pydanticai-poc ingest --source rules
uv run pydanticai-poc ingest --all
uv run pydanticai-poc import-folder --user alice
uv run pydanticai-poc chat --user alice
uv run pydanticai-poc ask --user alice --question "Welche Regeln gelten für ...?"
uv run pydanticai-poc evaluate --dataset /local/path/golden.json
```

Resolve folder paths and dummy role assignments from configuration. Support machine-readable output for evaluation and later API integration. Return nonzero exit codes for ingestion or execution failures; distinguish a successful insufficient-evidence answer from an infrastructure failure.

### Deployment and observability

- Use a pinned container image, uv lockfile, internal package/model artifacts, and locally configured endpoints.
- Provide a Quadlet container definition for the ingestion runner and a compatible systemd timer/service arrangement for nightly execution. Validate the exact mechanism against the installed Podman version. The interactive CLI can run on demand; no persistent web service is required yet.
- Mount source folders read-only and keep derived data/log volumes separate. Supply credentials via protected deployment configuration or secrets, not committed files or model context.
- Emit local structured logs containing request ID, source/generation, retrieval configuration, timings, model revision, validation failures, and answer status. POC content logging may include passages and answers through an explicit setting; credentials must never be logged.
- Disable external tracing/exporters. Add local reports for stale sources, conversion failures, failed refreshes, and model/database unavailability.
- Document backup/recovery responsibilities for the POC's derived state and how to rebuild from original sources. A model outage should produce an explicit error; a failed refresh may continue using the last valid generation with its timestamp disclosed.

## 13. Handover and production follow-up

Deliver implementation code, migrations, configuration examples, pytest suites, ingestion and evaluation commands, per-source retrieval reports, deployment files, and an operations runbook. Keep golden data, sensitive logs, credentials, and original documents outside version control.

The final report must distinguish implemented behavior, measured quality, unresolved limitations, and production work. Include representative German answers and assessment reports using approved/redacted examples.

Before production, replace dummy identity with SSO; define permission refresh/revocation semantics; add finer-grained ACL support where required; establish upload/log/conversation retention and redaction policies; validate concurrent users and resource limits; and review operational resilience and domain acceptance. The FastAPI layer should call the same application services with an authenticated `UserContext`, replacing CLI presentation and identity resolution without redesigning retrieval.

Use the available local skills first, and verify examples against the installed package versions. The `building-pydantic-ai-agents` skill's `references/ARCHITECTURE.md` includes provider selection and custom OpenAI-compatible endpoint configuration. Its `references/TOOLS-ADVANCED.md` and `references/TESTING-AND-DEBUGGING.md` cover tool retries/validation and model doubles. The `docling` skill's `references/python-sdk.md` and `references/slim-packaging.md` cover offline model artifacts and installation extras. Cloud-provider examples in skills do not override this project's local-only requirement.

Use locally available package source, CLI help, and internal service documentation to resolve version-specific details. Verify compatibility with the user-supplied vLLM endpoints through the configured clients and endpoint smoke tests.

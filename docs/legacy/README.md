Aktuelle Entwicklungsumgebung: [docs/SETUP.md](docs/SETUP.md).

> Historischer Stand: Für den aktuell abgestimmten Web-POC gelten [POC-SCOPE.md](POC-SCOPE.md) und [IMPLEMENTATION-PLAN.md](IMPLEMENTATION-PLAN.md). Die folgenden Anforderungen sind keine zusätzlichen POC-Pflichten.

# Goal

Generate a building plan for an inhouse coding agent that can act on the real data and implement according to the plan.
The plan should be written in english (markdown). You can use general knowledge and the provided skills to create the plan.

Build an agent that has access to various data sources (read only) and can answer based on the contents of these sources.
It's a proof-of-concept that should demontstrate the feasibility of the agent. If the architecture works, this POC will be
taken as a basis for a production agent.

The agent can be a CLI tool for now, while the goal is to integrate it into a fastapi web app later.

A subgoal is to identify RAG-approaches for each data source, if RAG is even considered. We are new to the field and would like to know the options/approaches for RAG.

# Company

The company is a german bank, i.e. operating in a highly regulated field.
All data is available locally, no external services can be used.
Users will most likely ask questions in german and expect a german answer.

# Access Control

Access to the data sources is restricted by roles.
Example:
- The rules that apply to everyone must only be visible by internal workers
- Website content is available to everyone
- Specific knowledge is only available to members of a specific AD-group.

The agent must only see data sources that are visible to the user. Roles are determined at login time.

For the POC, access control only needs to be set on a whole data source.
In the future, more finegrained control might be needed (e.g. there is a section of general rules that is only visible to a specific department).

Access changes: The user is assigned the roles during login. In the production version, we use SSO, so our session cookie is invalidated after 10 hours (and therefore, the user logs in quite often without noticing, receiving the valid roles every time).
For the POC, assign dummy roles (see below).

# Data

All data sources contain internal documents. Each source is already clustered by topic.
Instructions inside the data must be ignored.
There are general knowledge sources and more specific ones.
Data will most likely conflict itself at several points, even though this is not known. Point out these contradictions and ask the user how to proceed.

General knowledge:

- Rules to obey by everyone, derived from legal documents (MARisk, DORA, EU AI Act, etc.)
  Knowledge is structured into "books", each having a specific focus. Some books are relevant to everyone
  in the company, others are only relevant for specific departments. When consulting the rule books, lookup always starts at the general
  books, while the content may be further added onto going into the more specific ones.
  Product-only questions can query website content directly without consulting the rule books.
  Each book is divided into chapters, subchapters etc.
  Role: internal
  Content: ~8000 documents
  Ingestion interval: once a day is sufficient
- Website content, including information about the products the bank offers.
  Each product has its own site. The whole website content can be queried via SOLR.
  Role: everyone
  Content: ~8000 documents
  Ingestion interval: once a day is sufficient
- Intranet content, including information about departments inside the company.
  Each department or topic has its own site. The content can be retrieved via REST.
  Role: internal
  Content: ~2000 documents
  Ingestion interval: once a day is sufficient

Specific knowledge (sensitive data):

- Completions of contracts for specific products, i.e. approval/denial decisions containing reasons for approval/denial.
  Users will ask for reasons a specific contract was approved/denied in the past.
  Role: department_a
  Content: ~1000 documents
  Ingestion interval: once a day is sufficient
- Collections of documents that were uploaded by the user
  Role: only the user
  Content: ~100 documents per user
  Ingestion interval: at every upload
  for this poc, the documents can be provided in a separate folder, as a CLI tool should be build. The data should remain in the folder after ingestion.

The data source should be implemented one by one, starting with the general rules.
Depending on the source, the retrieval scores should be evaluated against a "golden" set of questions and answers, which will then be provided as json (question, answer, source(s)).
Golden-set citations will identify specific passages most of the time. Initial quality thresholds should be proposed in the plan and refined after baseline measurements.
Questions can be targeted to a specific data source (vacation -> general rules, product information -> website), but it should be possible to ask questions that require multiple data sources (e.g. "check if the description of the product (website) matches the company guidelines regarding text formulations (intranet)", or "check if all requirements from (general rules) are met in this document (uploaded by the user)"). The agent should read the rules and assess for each rule.
For rule-by-rule assessments, the agent should identify the applicable books and chapters and confirm the scope with the user before assessing each rule. Users may also specify the scope directly.
Please suggest a retrieval approach for each data source. Include your reasoning, so that is is understandable why you favoured the approach compared to others.

# Planned Data Sources

These are planned, but out of scope for this POC:

- JIRA
- Confluence
- Sharepoint

# Data Ingestion

Data can be preprocessed at night and stored in mysql/weaviate, if that helps to build a search index.
Old data must be discarded. If the indexing fails, just keep the previous data (that is, only delete the old if the new has been ingested correctly).
The original data must not be modified.

# Musts

- All data is read-only.
- The agents answers must be based on specific sources, which must be cited (source page/chapter/section)
- Conversation support: The agent must answer follow up questions intelligently, that includes searching for new information if needed.
- Conversations can be stored in memory in this POC.
- Accuracy is more important than speed, but the users favor speedy solutions.
- The application should be easily extensible with new data sources.
- Evidence should be taken from the sources, if available. If the data is insufficient to answer the question, tell the user and ask how to proceed.

# Logging

For this POC, debugging logs may contain sensitive source passages and answers.
Production requires stricter handling of sensitive data in logs; the production logging policy must be defined before deployment.

# Tech Stack

- linux (SLES 15) as operating system
- podman as a container runtime
- podman quadlets as a service manager
- python >= 3.11
- uv for project management
- pytest for tests
- fastapi for webservice
- pydantic ai for the agent logic
- docling for document processing
- models (all hosted via vLLM):
  - google gemma 4 31B
  - snowflake embedding model
  - qwen 3 reranker
- mysql as a relational database (already available)
- weaviate as a vector database, supporting semantic search/keyword search/hybrid search (already available)

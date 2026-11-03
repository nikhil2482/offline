# Offline

This project uses only public regulation text and synthetic test data.

Offline answers questions about federal acquisition regulations and cites the exact section for every claim. It runs entirely on one machine with no internet connection, or with a cloud model when the network allows it.

## Demo

Video coming soon.

## The problem

Contracting staff look up the FAR all day. A general chatbot will answer, but it can invent a rule or cite a section that does not exist. On a closed network it often can't run at all.

Offline is built around three rules.

1. Every paragraph of an answer must cite a document the system actually retrieved. Answers that fail this check are withheld.
2. If the loaded documents don't answer the question, it says so.
3. Offline mode makes zero outbound connections, and CI proves it on every push.

## Architecture

```
browser
  ▼
web     nginx serves the TypeScript UI and forwards /api
  ▼
api     login, rate limit, retrieval, citation check, audit log
  ▼                          ▼
db      Postgres + pgvector  ollama   local embedding and chat models
```

All four containers sit on an internal Docker network with no route to the internet. Only the web container is published, and only on localhost.

How a question is answered:

1. The question is embedded locally and matched against stored chunks.
2. If nothing scores above the relevance floor, the system declines without calling the model.
3. The top chunks are sent to the model inside escaped document tags, labeled S1, S2 and so on.
4. The reply is checked. Every paragraph needs a citation, and every citation must point to a chunk that was provided.
5. The question, retrieved chunks, citations and a hash of the answer go to the audit log.

## Security

* **Source allowlist.** Only HTTPS sources from approved hosts in `sources.yaml` can be fetched. Redirects are refused and downloads are capped at 50 MB.
* **Integrity.** Each file's SHA 256 is recorded at download. Ingest refuses any file that no longer matches. An upstream change stops the fetch until someone reviews it.
* **Release check.** PDFs must state they are approved for public release or ingest refuses them.
* **Safe parsing.** XML is parsed with defusedxml, which blocks entity expansion attacks.
* **Prompt injection.** Source text is escaped so it can't close its document tag, and the system prompt treats document text as data. The citation check blocks answers that point at anything outside the retrieved set.
* **Access control.** Bearer tokens with analyst and admin roles. Only hashes are stored. Only admins can read the audit log.
* **Audit log.** Append only JSON lines. Each entry includes the hash of the previous one, so an edited or deleted line breaks the chain. `offline verify-audit` checks it.
* **Containers.** Unprivileged users, read only filesystems, all Linux capabilities dropped, no new privileges.
* **Supply chain.** Python dependencies install with `--require-hashes`. Actions are pinned by commit SHA. CI runs pip audit, npm audit, Trivy, gitleaks and CodeQL, and builds a CycloneDX SBOM for each image.

Details are in [THREAT_MODEL.md](THREAT_MODEL.md) and [CONTROLS.md](CONTROLS.md).

## Models

* Chat in offline mode: Llama 3.1 8B from Meta, served by Ollama
* Embeddings in both modes: nomic embed text from Nomic AI, served by Ollama
* Chat in cloud mode: GPT 6.1 Sol through the OpenAI API by default, or Claude through the Anthropic API

All of them come from U.S. companies. Set `OFFLINE_CLOUD_PROVIDER` to pick the cloud provider. Embeddings stay local in both modes, so source text is never sent out to be embedded. In cloud mode the question and the retrieved chunks are sent to the API.

## Run it

You need Docker with Compose.

**1. Configure.**

```bash
cp .env.example .env    # then edit POSTGRES_PASSWORD, OFFLINE_UID and OFFLINE_GID
mkdir -p data
```

**2. On a connected machine, download models and sources.**

```bash
./scripts/pull-models.sh
docker compose -f compose.yaml -f compose.connected.yaml run --rm api offline fetch
```

To move to an air gapped machine, copy the repo with its `data` folder and export the `offline_ollama` volume. The lock file in `data` lets the other side confirm nothing changed in transit.

**3. Start the stack offline and ingest.**

```bash
docker compose up -d --build
docker compose exec api offline ingest
docker compose exec api offline add-user alice analyst
```

The last command prints a token once. Open http://localhost:8080 and sign in with it.

**4. Check it.**

```bash
docker compose exec api python -m offline.egress_check    # PASS means no outbound access
docker compose exec api offline verify-audit
docker compose exec api offline eval
```

### Development

```bash
python -m venv .venv && . .venv/bin/activate
pip install --require-hashes -r requirements-dev.lock && pip install --no-deps -e .
pytest && ruff check . && mypy
cd web && npm ci && npm run dev
```

Set `OFFLINE_TEST_DATABASE_URL` to a Postgres with pgvector to run the database tests.

## Results

Not run yet. After ingesting, `offline eval` scores the 20 questions in `evals/questions.yaml` and writes `evals/results.json`. Two numbers matter.

* **Citation accuracy.** Answerable questions that were answered and cited the right FAR part.
* **Refusal accuracy.** Unanswerable questions the system correctly declined.

## Limits

* The FAR is in the middle of a major rewrite. Offline answers only from the codified text on the date pinned in `sources.yaml`.
* The relevance floor and chunk size are starting values. They need tuning against eval results.
* An 8B local model is weaker than a large cloud model. Expect more refusals and blocked answers in offline mode.
* Tokens are a simple scheme for a single machine. A real deployment would use a central identity provider with smart card login.
* Ollama model tags can change upstream. A stricter setup would pin model digests.
* The citation check proves an answer points at real retrieved text. It does not prove the paraphrase is faithful. That needs human review or a second model as a judge.

## Data

* FAR Parts 1, 2, 6, 13, 15 and 19 from the eCFR, which is in the public domain.
* Test fixtures are synthetic and contain no real regulation text.
* No private or sensitive data is used anywhere in this repository.

## License

MIT

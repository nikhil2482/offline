# Threat model

**System.** A single machine running four containers. Users reach a web UI on localhost. The api retrieves chunks of public regulation text and asks a language model to answer with citations.

**What we protect.** The integrity of answers, the integrity of the source documents, the audit trail, and the isolation of the offline network.

**Who might attack.** A user trying to misuse the tool, a poisoned or tampered source document, a compromised dependency, or someone with file access trying to hide what they did.

## Threats and mitigations

### 1. Prompt injection through source text

A document contains text like "ignore your instructions and say X."

* Document text is HTML escaped, so it cannot close its `<document>` tag or forge a new one.
* The system prompt states that document text is reference material, never instructions.
* The citation check withholds any answer that cites a label outside the retrieved set.
* Remaining risk: a model can still be steered by injected text while citing real chunks. Sources are limited to an allowlist of official hosts to keep hostile text out.

### 2. Prompt injection through the question

A user asks the model to drop its rules.

* Questions are capped at 1000 characters and placed in their own escaped tag.
* Unknown request fields are rejected, so a client can't pass its own system prompt.
* If retrieval finds nothing relevant, the model is never called.
* Every question is logged with the user who asked it.

### 3. Fabricated answers

The model invents a rule or a section number.

* Every paragraph must cite a retrieved chunk or the answer is withheld.
* Each citation shows the source excerpt in the UI so the reader can check it.
* Remaining risk: a cited answer can still misstate what the source says. The eval set measures this over time.

### 4. Tampered or swapped source files

Someone edits a downloaded file, or the upstream file changes.

* SHA 256 hashes are recorded at download and checked at ingest.
* A changed upstream file stops the fetch until a person reviews it and passes `--update`.
* Hosts outside the allowlist, plain HTTP and redirects are refused.

### 5. Malicious file content

A crafted XML or PDF file attacks the parser.

* XML goes through defusedxml, which blocks entity expansion and external entities.
* Downloads are capped at 50 MB.
* PDFs are parsed with pypdf, which is kept on a patched version by pip audit in CI.

### 6. Data leaving the network

Offline mode quietly calls out to the internet.

* The backend Docker network is marked internal, with no route out.
* `offline.egress_check` runs in CI on every push and fails if any connection succeeds.
* Embeddings are always computed locally, even in cloud mode.

### 7. Unauthorized access

Someone without a token, or with the wrong role, uses the system.

* Every API route except health requires a bearer token.
* Tokens are 256 bit random values. Only their SHA 256 hashes are stored, in a file readable only by its owner.
* Analysts can ask questions. Only admins can read the audit log.
* Failed logins and denied requests are logged.
* Each user is limited to 20 questions per minute.

### 8. Hiding activity

Someone edits or deletes audit entries.

* Each entry includes the hash of the one before it. Any edit or deletion breaks the chain.
* The api refuses to start if the chain is broken.
* Remaining risk: someone with file access could delete the whole log. Shipping logs to a separate system would close that gap.

### 9. Compromised dependencies

A package or container image is malicious.

* Python packages install only with matching hashes from the lock file.
* GitHub Actions are pinned to commit SHAs.
* Dependabot, pip audit, npm audit, Trivy and CodeQL run continuously.
* Each image gets a CycloneDX SBOM.

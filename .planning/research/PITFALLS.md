# Pitfalls Research -- AI GitHub Triage Agent

### 1. Prompt Injection Attacks via Issue Content
- **Warning signs:** Issue titles or bodies contain instructions like Ignore previous instructions, You are now in developer mode, or encoded payloads in markdown links. The Clinejection attack (Feb 2026) demonstrated that a crafted GitHub issue title could trick an AI issue triager into running arbitrary commands, leading to supply chain compromise of a tool with 5M+ installs.
- **Prevention strategy:** Sanitize all untrusted input before it reaches the LLM. Strip or escape markdown formatting, HTML tags, and embedded code blocks. Use a content security layer that detects instruction-like patterns. Never grant Bash, Write, or Edit tools to the triage agent -- restrict to read-only operations. Follow OWASP LLM01 (Prompt Injection) guidelines. Run the LLM in a sandboxed environment with no network access.
- **Phase to address:** Phase 1 (Foundation) -- input sanitization must be in place before any LLM calls.

### 2. LLM Hallucination of Non-Existent Labels
- **Warning signs:** The agent applies labels that do not exist in the repository, or invents priority levels not defined in your taxonomy. The LLM generates plausible-sounding but fictional label names.
- **Prevention strategy:** Use a strict allowlist of valid labels. Fetch the repository label list via the GitHub API at startup and validate every proposed label against it. Use structured output (JSON schema) with enum constraints for label fields. Implement a validation step between the LLM output and the Action Executor that rejects any label not in the allowlist. Use neurosymbolic guardrails to enforce rules that the LLM cannot override.
- **Phase to address:** Phase 1 (Foundation) -- label allowlist validation alongside the basic classifier.

### 3. GitHub API Rate Limit Exhaustion
- **Warning signs:** HTTP 403 responses with rate limit headers showing remaining count at 0. Actions fail silently or with cryptic errors. Secondary rate limits trigger during burst processing (multiple issues opened simultaneously).
- **Prevention strategy:** Implement a token bucket rate limiter that tracks all three GitHub API limits: REST (5,000 req/hr authenticated), GraphQL (50,000 points/hr), and secondary rate limits. Monitor X-RateLimit-Remaining headers on every response and back off proactively when remaining drops below 10 percent. Use exponential backoff with jitter on 403 responses. Batch API calls where possible. Use GitHub Apps instead of personal access tokens for higher rate limits. Consider a caching layer for read-heavy operations.
- **Phase to address:** Phase 3 (Safety and Control) -- rate limit management is part of the safety layer.
### 4. Webhook Duplicate Delivery and Idempotency Failures
- **Warning signs:** The same issue gets labeled twice, duplicate comments are posted, or the audit log shows multiple triage runs for the same issue. GitHub delivers webhooks with at-least-once semantics, meaning duplicates are guaranteed under load, network blips, or provider retries.
- **Prevention strategy:** Use the X-GitHub-Delivery header as a unique idempotency key. Implement insert-first deduplication with a database unique constraint on the delivery ID -- this is the only race-condition-free pattern. The check-then-act pattern has a TOCTOU race condition that fails under concurrent delivery. Store the delivery ID before processing begins, not after. Use Redis SETNX for high-throughput scenarios. At the infrastructure level, consider an event gateway that handles deduplication before events reach your application.
- **Phase to address:** Phase 1 (Foundation) -- idempotency layer must be in place before any processing logic.

### 5. Vector DB Embedding Dimension Mismatches
- **Warning signs:** Vector search returns empty results or throws dimension mismatch errors. This is the number 1 cause of silent failures in vector search systems. Switching embedding models mid-project without recreating the index causes all existing vectors to become incompatible.
- **Prevention strategy:** Declare the embedding dimension as a single source of truth in configuration. Validate at startup: generate a test embedding and verify its length matches the index dimension. Log the embedding model name and version alongside each vector. If you need to switch models, create a new index and re-embed all documents -- never try to modify an existing index dimension.
- **Phase to address:** Phase 2 (Intelligence) -- vector search setup must include dimension validation from day one.

### 6. Context Window Overflow with Long Issues
- **Warning signs:** The LLM returns truncated responses, ignores instructions at the end of the prompt, or produces increasingly unreliable outputs as issue threads grow. API returns HTTP 400 with context length exceeded errors. Latency increases as prompts get longer.
- **Prevention strategy:** Implement smart chunking: split long issue bodies into semantic chunks and process the most relevant sections. Use a sliding window that keeps the N most recent comments and drops older ones. When context reaches 70-80 percent capacity, trigger LLM-based summarization of earlier conversation segments. Set explicit token budgets for each component. Monitor latency as an early warning signal.
- **Phase to address:** Phase 2 (Intelligence) -- context management is needed as soon as you process real-world issues of varying lengths.
### 7. Non-English Issue Handling Failures
- **Warning signs:** Issues written in non-English languages receive incorrect labels, wrong priority scores, or are misclassified. The LLM performs significantly worse on issues in languages other than English due to training data imbalance. Mixed-language issues cause inconsistent processing.
- **Prevention strategy:** Use a multilingual LLM or a language detection step that routes non-English issues to a specialized model. Test the triage system with issues in your project most common non-English languages before deployment. Include multilingual examples in your evaluation dataset. Consider a translation step for non-English issues before classification. Monitor classification accuracy by language and set up alerts for degradation in non-English performance.
- **Phase to address:** Phase 2 (Intelligence) -- multilingual handling should be tested during the intelligence phase before full deployment.

### 8. Demo-Day Failures (Live Demo Risks)
- **Warning signs:** The agent works perfectly in testing but fails during the live demo. Common causes include: LLM API rate limits hit during demo, network connectivity issues, the demo repository has no historical issues for vector search, the LLM produces unexpected output for the specific demo issue, or the GitHub API returns an error at the worst moment.
- **Prevention strategy:** Build a canned demo mode that replays pre-recorded triage decisions with realistic timing. Create a fallback path that bypasses the LLM entirely and uses rule-based classification. Pre-populate the vector database with sample issues so similarity search works during the demo. Test the exact demo scenario multiple times before the presentation. Have a recorded video backup in case live demo fails. Implement comprehensive error handling that degrades gracefully rather than crashing. Use a dedicated demo repository that you control completely.
- **Phase to address:** Phase 4 (Observability) -- demo hardening is the final phase, but plan for it from the start by designing for graceful degradation.

---

## Cross-Cutting Mitigation Strategies

| Strategy | Applies To | Implementation |
|----------|-----------|----------------|
| Input sanitization pipeline | Prompt injection, context overflow | Strip markdown, HTML, detect instruction patterns |
| Structured output validation | Hallucinated labels, non-English failures | JSON schema with enums, allowlist validation |
| Rate limit awareness | API exhaustion, demo failures | Token bucket, proactive backoff, monitoring |
| Idempotency by design | Duplicate webhooks | X-GitHub-Delivery as unique key, insert-first pattern |
| Configuration-driven dimensions | Vector DB mismatches | Single source of truth, startup validation |
| Token budget management | Context overflow | Explicit allocation per component, sliding window |
| Multilingual evaluation | Non-English failures | Language detection, specialized models, translation fallback |
| Graceful degradation | Demo failures | Canned mode, rule-based fallback, recorded backup |
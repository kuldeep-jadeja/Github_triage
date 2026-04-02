# Features Research — AI GitHub Triage Agent

> Compiled: 2026-04-02
> Sources: GitHub blog, Dosu.dev, Cotera, GitHub Docs, Probot ecosystem, agentic patterns research, CHAOSS metrics, issue-metrics tool, OpenClaw/ClawTriage

---

## Table Stakes

Features every AI triage product must have. Without these, users will not adopt the tool.

- **Auto-labeling** — Classify issues by type (bug, feature, question, docs) and domain (frontend, backend, API) based on title and body content. Uses LLM understanding of natural language, not keyword matching. Complexity: Low. Every competitor does this (Dosu, Cotera, GitHub's own AI intake tool, Probot Issue Labeler).

- **Duplicate detection** — Identify when a new issue is likely a duplicate of an existing open or recently-closed issue, even when described with different wording. Must link to the original. Complexity: Medium. This is the #1 value-add cited by maintainers — duplicate issues are the biggest time sink. Cotera reports catching duplicates that manual triage missed for months.

- **Priority suggestion** — Assign priority labels (P0–P3 or critical/high/medium/low) based on impact analysis: number of affected users, revenue impact, workaround availability, and reaction counts. Complexity: Low-Medium. Consistent priority assignment is a key pain point — humans are inconsistent based on fatigue and recency bias.

- **Owner/team routing** — Suggest which team or maintainer should own an issue based on codebase area, file structure analysis, and historical assignment patterns. Complexity: Medium. Requires understanding of repo structure and code ownership. Cotera's agent reads file structure to determine component ownership.

- **Actionable vs. needs-more-info classification** — Determine whether an issue has enough information to act on, or if it needs clarification from the reporter. Complexity: Low. This is GitHub's own AI-powered issue intake tool's primary function.

- **Issue summarization** — Generate concise 2–3 sentence summaries of long issue bodies so maintainers can triage faster without reading every word. Complexity: Low. GitHub's Copilot SDK demo (IssueCrush) shows this as the core value proposition.

- **Response drafting** — Generate suggested replies to issues (requesting more info, acknowledging a bug, explaining why something is not a bug) that maintainers can review, edit, and approve before posting. Complexity: Medium. Dosu offers "response previews" as a configurable feature.

- **Configurable automation levels** — Allow teams to choose which parts of triage are fully automatic vs. suggestion-only. Complexity: Medium. Dosu's modular approach lets teams use only auto-labeling, only deduplication, or full automation.

---

## Differentiators

Features that create competitive advantage and are not universally available.

- **Multi-repo context awareness** — Analyze issues across multiple repositories in an organization, detecting cross-repo duplicates and related issues. Complexity: High. Most tools work per-repo. Cotera's multi-repo audit agent processes issues across 4 repos simultaneously.

- **Commit/PR correlation** — Check recent commits and open PRs to see if someone is already working on the reported issue. Complexity: High. Cotera's agent does this — it reads recent commits and open PRs to avoid assigning work that's already in progress. This is a massive time-saver that basic labelers cannot do.

- **Reasoning traces / explainability** — Show WHY the AI made each classification decision: which signals it used, which existing issues it compared against, what confidence level it has. Complexity: Medium. No major competitor currently provides this. Builds trust and helps maintainers learn from the AI's reasoning.

- **Confidence scoring with escalation** — Provide a confidence score for each decision and automatically escalate low-confidence classifications for human review. Complexity: Medium. Cordum's Pattern 2 (exception-based escalation) shows this is a proven pattern. Agents should escalate when confidence drops below a threshold (e.g., 0.7).

- **Graduated autonomy** — Start with maximum oversight and gradually grant more autonomy as the AI demonstrates competence over time, with automatic demotion on errors. Complexity: High. Cordum's Pattern 3 shows this pattern. New agents begin supervised, earn semi-autonomous status after 50+ successful actions with <2% error rate.

- **Real-time triage dashboard** — Live view of incoming issues, AI decisions, pending approvals, and team workload. Not just a GitHub Issues filter — a purpose-built dashboard with triage-specific views. Complexity: Medium-High. IssueCrush shows a swipeable card UI concept. No competitor has a polished real-time dashboard as a core product.

- **Multi-language / cross-lingual support** — Handle issues filed in languages other than English, including translation and culturally-aware classification. Complexity: Medium. Important for global OSS projects (React, VS Code, Kubernetes have significant non-English issue volume).

- **Trend detection and momentum tracking** — Detect when a low-priority issue is gaining traction (reactions, comments, duplicate reports) and suggest re-prioritization. Complexity: Medium. Cotera notes their agent doesn't handle this well — it's a gap in the market.

- **Knowledge base integration** — Build a project-specific knowledge base from docs, past issues, PRs, and discussions to ground triage decisions in project context rather than generic patterns. Complexity: Medium-High. Dosu builds knowledge from "Data Sources" within the project.

- **Slack/Teams integration with approval workflows** — Send triage decisions to team chat with approve/reject buttons, enabling async review without opening GitHub. Complexity: Medium. Cordum's HITL pattern shows Slack integration as the primary approval channel.

- **Audit trail and decision history** — Log every AI triage decision with timestamp, reasoning, and human override history. Enables compliance, debugging, and model improvement. Complexity: Low-Medium. Cordum emphasizes immutable audit trails as a core requirement.

- **Cost-aware processing** — On-demand summarization (not preemptive), caching of results, and graceful degradation when AI services are unavailable. Complexity: Medium. IssueCrush demonstrates on-demand summaries with fallback to metadata-based summaries.

---

## Anti-Features

Things to deliberately NOT build, with rationale.

- **Auto-closing issues without human review** — Never automatically close issues. Users file issues to be heard; auto-closing creates frustration and erodes trust. Even high-confidence duplicates should be flagged, not closed. The Cotera case study explicitly notes: "The agent doesn't respond to issues. It triages them. The actual human response still comes from the team."

- **Auto-assignment without opt-in** — Never assign issues to maintainers without explicit opt-in. Assignment creates obligations and notification noise. Suggest owners, let humans confirm. Unsolicited assignment is the #1 complaint about existing automation tools.

- **Auto-responding to issues without review** — Never post AI-generated comments to issues without human approval. Users deserve to interact with a person when they take the time to file a report. AI-generated responses that are wrong or tone-deaf damage project reputation permanently.

- **Black-box decisions without explanation** — Never make triage decisions that cannot be explained. If the AI labels something as "duplicate" without showing which issue and why, maintainers cannot trust it and will disable the tool.

- **One-size-fits-all labeling schemes** — Never impose a fixed label taxonomy. Every project has its own conventions. The tool must adapt to existing labels, not replace them.

- **Aggressive notification spam** — Never notify maintainers about every single decision. Batch notifications, respect quiet hours, and only escalate when human input is genuinely needed. Approval fatigue is a real problem — Cordum's research shows reviewe

rs rubber-stamp when overwhelmed.

- **Permanent autonomous operation without oversight** -- Never run fully autonomously indefinitely without periodic human review checkpoints. Even mature agents need sampled audits (Cordum Pattern 4) to catch drift.

---

## Competitive Landscape

### Existing GitHub Triage Bots

| Tool | Core Features | Limitations |
|------|--------------|-------------|
| **Probot Issue Labeler** | Label issues based on title/body against a list of defined labels. Uses regex/keyword matching. | No LLM understanding. No duplicate detection. No priority assignment. No reasoning. |
| **Probot Auto-labeler** | Labels PRs based on matched file patterns. | PRs only, not issues. File-path based only. |
| **Issue Label Bot** (mlbot.net) | ML-based automatic labeling. Available on GitHub Marketplace. | Labeling only. No dedup, no routing, no summarization. |
| **GitHub AI-Powered Issue Intake** (official) | Classifies issues as actionable vs. needs-more-info. Triggered by  label. Suggests actions. | GitHub Action-based, not real-time. Limited to binary classification + suggestions. No dedup or routing. |
| **Dosu** (dosu.dev) | Auto-labeling, issue deduplication, response previews, knowledge base from project data sources. Modular automation levels. | Enterprise-focused. No multi-repo context. No commit/PR correlation. |
| **Cotera** (cotera.co) | Multi-repo audit agent. Reads commits/PRs for context. Priority assignment (P0-P3). Duplicate detection with reasoning. Owner routing. | Focused on audit workflows. No real-time dashboard. No graduated autonomy. |
| **OpenClaw / ClawTriage** | GitHub issue triage skill. 1,240 community stars. | Skill-based, not a standalone product. Limited feature set. |
| **ClawTriage** (GriffinAtlas) | AI-powered PR triage. Dedup, quality scoring, vision alignment as GitHub Action. | PR-focused, not issue-focused. New project (0 stars). |
| **gh-aw** (GitHub Agentic Workflows) | Automated triage for reducing unlabeled issues. 4.2K stars. Go-based. | Internal GitHub tool. Limited public documentation. |

### AI Coding Assistants and Issue Management

| Tool | Issue-Related Features |
|------|----------------------|
| **GitHub Copilot** | Issue summarization via Copilot SDK (IssueCrush demo). AI-powered issue intake tool (GitHub Action). No autonomous triage agent. |
| **Cursor** | IDE-focused. Can reference issues in chat. No autonomous issue triage or management. |
| **Devin** | Autonomous coding agent. Can work on issues end-to-end (read, plan, implement). Not a triage tool -- it is an issue resolver. |
| **Claude Code** | Can read and work on issues via CLI. No triage-specific features. |
| **GitHub Copilot Workspace** | Issue-to-PR workflow. Converts issues into implementable plans. Not triage -- it is issue resolution. |

### Key Gap Analysis

The market has two distinct categories:
1. **Labeling bots** (Probot, Issue Label Bot) -- cheap, dumb, keyword-based
2. **Issue resolvers** (Devin, Copilot Workspace) -- expensive, autonomous, end-to-end

**The gap**: Intelligent triage agents that sit between these extremes -- smarter than labelers, less expensive/autonomous than resolvers. This is where Dosu and Cotera compete, and where our product should position itself.

---

## Human-in-the-Loop Approval Workflows

Based on Cordum 5 production patterns (validated in production, 2026):

### Pattern 1: Pre-execution Approval Gate (Highest Safety)
- **Use for**: Auto-closing, auto-assigning, auto-responding -- any irreversible action
- **Flow**: AI proposes, policy engine evaluates, human approves/denies, action executes
- **Implementation**: Risk-tiered routing. Low-risk actions (labeling) pass through. High-risk (closing, responding) require approval.

### Pattern 2: Exception-Based Escalation (Balanced)
- **Use for**: Routine triage with occasional edge cases
- **Flow**: AI operates autonomously within confidence bounds, escalates when confidence below threshold
- **Implementation**: Confidence scoring on every decision. Below 0.7 goes to human review queue. Above 0.7 auto-applies.

### Pattern 3: Graduated Autonomy (Trust Building)
- **Use for**: New deployments, building maintainer trust over time
- **Flow**: Start supervised, earn autonomy through demonstrated competence, demote on errors
- **Implementation**: Level 0 (all decisions reviewed) to Level 1 (labeling auto, rest reviewed) to Level 2 (routine auto, sensitive reviewed) to Level 3 (most auto, destructive gated)

### Pattern 4: Sampled Audit (Scale)
- **Use for**: High-volume repos where reviewing every decision is impractical
- **Flow**: AI operates autonomously, random subset flagged for post-hoc human review
- **Implementation**: Stratified sampling -- higher-risk decisions sampled at higher rates (3x for prod-impacting, 0.5x for docs).

### Pattern 5: Post-execution Output Review (Safety Net)
- **Use for**: AI-generated responses and summaries before they reach users
- **Flow**: AI generates content, safety check, human review, publish
- **Implementation**: All drafted responses held for review. Summaries shown with AI-generated badge.

### Recommended Approach for Our Product
- **Default**: Pattern 2 (exception-based escalation) -- autonomy for safe operations (labeling, dedup flagging), escalation for uncertain decisions
- **Configurable**: Teams can shift toward Pattern 1 (more gates) or Pattern 3 (graduated autonomy)
- **Always**: Pattern 5 for any user-facing output (never auto-post)
- **At scale**: Pattern 4 kicks in automatically when volume exceeds threshold

---

## Dashboard Metrics That Matter

Based on CHAOSS project metrics, GitHub issue-metrics tool, and maintainer interviews from case studies:

### Operational Metrics (Daily Triage)
| Metric | Why It Matters | Target |
|--------|---------------|--------|
| **Time to first label** | How quickly issues get categorized. Measures triage responsiveness. | Under 5 minutes (AI) vs. 18 hours (manual, per Cotera) |
| **Time to assignment** | How quickly issues reach the right person. | Under 5 minutes (AI) vs. 26 hours (manual, per Cotera) |
| **Unlabeled issue count** | Backlog health indicator. Rising count = triage bottleneck. | Trending toward 0 |
| **Stale issue count** | Issues with no activity for 30+ days. Indicates neglected areas. | Decreasing |
| **AI decision accuracy** | Percentage of AI classifications confirmed or not overridden by humans. | Over 90 percent (Cotera achieved 47/53 = 89 percent in week 1) |
| **Override rate** | How often humans change AI decisions. High rate = model needs tuning. | Under 10 percent |

### Quality Metrics (Weekly/Monthly)
| Metric | Why It Matters | Target |
|--------|---------------|--------|
| **Duplicate detection rate** | Percentage of duplicates caught before they sit open. | Over 95 percent within first week |
| **False positive rate** | Issues incorrectly flagged as duplicates or wrong category. | Under 5 percent |
| **Response quality score** | Maintainer rating of AI-drafted responses (thumbs up/down). | Over 80 percent positive |
| **Confidence distribution** | Histogram of AI confidence scores. Bimodal = good calibration. | Most decisions above 0.7 or below 0.3 |

### Health Metrics (Monthly/Quarterly)
| Metric | Why It Matters | Target |
|--------|---------------|--------|
| **Maintainer time saved** | Hours per week no longer spent on manual triage. | 2-3 hours/week per senior engineer (per Cotera) |
| **Issue resolution time** | End-to-end time from open to close. Triage is the first step. | Decreasing trend |
| **Contributor satisfaction** | Do contributors feel heard? Measured via response time perception. | Issues labeled within minutes improves perception dramatically |
| **Backlog growth rate** | Is the backlog shrinking, stable, or growing? | Stable or decreasing |
| **AI cost per issue** | API cost divided by issues processed. Important for sustainability. | Decreasing as caching improves |

### Dashboard UX Requirements
- **At-a-glance view**: Current unlabeled count, todays triage decisions, accuracy rate
- **Decision queue**: Pending human reviews sorted by priority/urgency
- **Trend charts**: Time-to-label, time-to-assignment over time
- **Per-repo breakdown**: Multi-repo teams need to see which repos need attention
- **AI performance panel**: Accuracy, override rate, confidence distribution
- **Configurable alerts**: Notify when unlabeled count exceeds threshold or accuracy drops

---

## Architecture Recommendations

Based on research findings:

1. **Server-side AI processing** -- Never run LLM calls client-side. IssueCrush demonstrates server-side pattern with graceful degradation. Keeps credentials secure and enables caching.

2. **On-demand, not preemptive** -- Generate summaries and classifications when issues are created or viewed, not in bulk. Keeps costs down and avoids wasted processing.

3. **Cache aggressively** -- Once an issue is classified, cache the result. If the user revisits, serve cached data immediately. No second API call needed.

4. **Graceful degradation** -- When AI services are unavailable, fall back to rule-based classification or metadata-only summaries. AI should accelerate triage, not be a single point of failure.

5. **Webhook-driven** -- Listen to GitHub webhook events (issue opened, edited, labeled) rather than polling. Real-time response is a key differentiator.

6. **Policy-as-configuration** -- Define triage rules, risk tiers, and approval requirements in version-controlled config (YAML), not hardcoded. Enables teams to customize without code changes.

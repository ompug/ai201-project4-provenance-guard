# ai201-project4-provenance-guard

Provenance Guard is a Flask API for AI content attribution. It accepts creator submissions, combines multiple detection signals into a confidence score, returns a plain-language transparency label, supports appeals, rate-limits submissions, and records a structured audit trail.

## Features

- `POST /submit` for text attribution
- three-signal ensemble detection
- confidence scoring with uncertainty handling
- plain-language transparency labels
- `POST /appeal` workflow with audit history
- rate limiting with `Flask-Limiter`
- structured SQLite audit log with `GET /log`
- verified human provenance certificate
- analytics dashboard
- metadata-based multi-modal submission path

## Setup

1. Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Create `.env` from `.env.example` and add your real Groq key:

```bash
cp .env.example .env
```

4. Run the app:

```bash
python -m flask --app app run
```

The API will be available at `http://127.0.0.1:5000`.

## Architecture Overview

A submission enters `POST /submit`, where the API validates the payload and assigns a `content_id`. The raw text then goes through three signals: a Groq-based holistic classifier, a stylometric heuristic scorer, and a lexical formality scorer. Their outputs are combined into a single confidence score, translated into an attribution category plus a reader-facing label, stored in SQLite, logged in the audit trail, and returned as structured JSON.

An appeal enters `POST /appeal` with a `content_id` and the creator's reasoning. The content status is updated to `under_review`, the appeal is written as a structured audit event alongside the original classification, and the response confirms that review is pending.

## Detection Signals

### 1. Groq LLM signal

- Measures: holistic style, generic phrasing, overly balanced "AI voice"
- Why I chose it: it captures semantic and stylistic clues that simple heuristics cannot
- What it misses: formal human essays, non-native but polished writing, carefully edited drafts
- Output: `ai_likelihood` from `0.0` to `1.0` plus a short rationale

### 2. Stylometric signal

- Measures: sentence length variance, type-token ratio, punctuation density
- Why I chose it: AI text is often structurally more uniform than human writing
- What it misses: poetry, very short submissions, dialogue-heavy writing, bullet lists
- Output: normalized `ai_likelihood` plus underlying metrics

### 3. Lexical formality signal

- Measures: density of stock transition phrases and formulaic formal connectors
- Why I chose it: many AI-generated paragraphs overuse scaffolding phrases like `furthermore` and `it is important to note`
- What it misses: academic human prose, business communication, technical reports
- Output: normalized `ai_likelihood` plus phrase-hit metrics

## Confidence Scoring

Each signal returns `ai_likelihood` in `[0, 1]`, where higher means more likely AI-generated.

### Ensemble formula

```text
combined = (groq * 0.45) + (stylometric * 0.30) + (lexical * 0.25)
```

### Uncertainty handling

If the three signals disagree strongly, the score is pulled toward `0.50` instead of letting one signal dominate:

```text
if max(signals) - min(signals) > 0.35:
    combined = (combined * 0.7) + (0.50 * 0.3)
```

This reflects the project design choice that false positives are worse than false negatives.

### Thresholds

- `confidence >= 0.72` -> `likely_ai`
- `confidence <= 0.38` -> `likely_human`
- otherwise -> `uncertain`

### Validation examples

I tested the scoring with clearly different writing styles and inspected the individual signal scores in the API response.

Low-score human example:

```text
"ugh. long day. burned toast, missed class, spilled coffee on my notes, then laughed about it because what else was i gonna do?"
```

- Result: `likely_human`
- Confidence: `0.324`

Lower-confidence / uncertain example:

```text
"still thinking about that awful toast from this morning. somehow the jam made it worse."
```

- Result: `uncertain`
- Confidence: `0.423`

Higher-score AI-leaning formal example tested during development:

```text
"Furthermore, it is important to note that the system should support responsible deployment. Furthermore, it is important to note that stakeholders should support responsible deployment. Furthermore, it is important to note that various sectors should support responsible deployment. Furthermore, it is important to note that modern society should support responsible deployment."
```

- Result during fallback-only testing: `uncertain`
- Confidence: `0.668`
- Note: with no `GROQ_API_KEY` configured, the Groq signal intentionally falls back to `0.5`, which compresses the top end of the score range. Adding a real key allows the LLM signal to distinguish this case more strongly.

## Transparency Labels

The system has three written label variants:

- High-confidence AI: `"Likely created with AI assistance. Multiple checks agree, and we are confident in this assessment."`
- Uncertain: `"Origin unclear. We could not confidently tell whether a person or AI wrote this. The creator can request a human review."`
- High-confidence human: `"Likely written by a person. Multiple checks agree, and we are confident in this assessment."`

For verified creators, the label is prefixed with:

```text
Verified human creator -
```

Example verified label:

```text
Verified human creator - Origin unclear. We could not confidently tell whether a person or AI wrote this. The creator can request a human review.
```

## Appeals Workflow

Creators can contest a decision by sending:

```json
{
  "content_id": "existing-content-id",
  "creator_reasoning": "I wrote this myself from personal experience."
}
```

When an appeal is received, the API:

1. looks up the original content
2. updates `status` to `under_review`
3. records a structured appeal event in the audit log
4. returns a confirmation response

The audit log shows both the original classification and the later appeal for the same `content_id`.

## Audit Log

The audit log is stored in SQLite and exposed with `GET /log`. Each classification row includes:

- timestamp
- content ID
- creator ID
- attribution
- confidence
- label
- individual signal scores
- status

Appeal rows additionally include `appeal_reasoning` and `event_type: appeal`.

Example fields visible in the log:

```json
{
  "content_id": "dd0e74b9-3fa1-4221-9d67-0fcfa7247710",
  "event_type": "appeal",
  "attribution": "uncertain",
  "confidence": 0.412,
  "status": "under_review",
  "appeal_reasoning": "I wrote this myself from personal experience, and the style is informal because it came from my notes app."
}
```

## Rate Limiting

The submission endpoints use:

```text
10 per minute; 100 per day
```

Reasoning:

- a normal writer may submit several drafts in a short burst
- `10 per minute` still allows revision-heavy testing
- `100 per day` is generous for normal usage but discourages mass probing or flood attempts

Example rate-limit behavior from testing:

```text
200
200
200
200
200
200
200
200
200
200
429
429
```

## Stretch Features

### Ensemble detection

The API exposes all three signal scores in both the response body and the audit log:

- `groq_score`
- `stylometric_score`
- `lexical_score`

Conflicts are handled through documented weighting and disagreement dampening.

### Provenance certificate

`POST /certificate/verify` lets a creator submit a short human writing sample. If the sample is classified as `likely_human` at or below `0.38`, the creator earns a verified-human badge. Future submissions from that creator return `verified: true` and a label prefixed with `Verified human creator -`.

### Analytics dashboard

`GET /dashboard` renders a simple HTML dashboard with at least three required metrics:

- detection pattern across `likely_ai`, `likely_human`, and `uncertain`
- appeal rate
- average confidence score

It also shows total submissions and verified-creator count.

### Multi-modal support

`POST /submit/metadata` accepts:

- `content_type: "image_description"`
- `content_type: "structured_metadata"`

The pipeline converts the metadata into analyzable descriptive text and then runs the same three-signal attribution flow.

## Known Limitations

- Formal academic prose may be misclassified as AI-leaning because both the lexical formality signal and the LLM signal can treat polished transitions and balanced structure as suspicious.
- Repetitive poetry or chant-like writing may be pushed toward AI by the stylometric heuristics because low variance and repeated vocabulary are intentional artistic choices.
- Very short submissions provide weak stylometric evidence, so those results lean more heavily on the other signals and often stay `uncertain`.

## Spec Reflection

The spec helped most with confidence design because it forced me to decide what `uncertain` should mean before I wrote code. That made the disagreement-dampening rule straightforward to implement instead of retrofitting uncertainty after the fact.

The main implementation divergence was that I expanded from the required two signals to a three-signal ensemble so I could satisfy the ensemble stretch feature cleanly inside the same pipeline. That changed the response shape slightly, but it made the README and audit log more informative.

## AI Usage

### Instance 1: initial Flask and storage scaffold

- I asked the AI to help structure the Flask app, submission route, and SQLite storage layer based on the planning document.
- The output gave me a useful first pass for route organization and data flow.
- I revised it by separating logging and content persistence, adding explicit `content_id` handling, and making the audit entries structured enough for rubric visibility.

### Instance 2: scoring and heuristics

- I used AI assistance to speed up the first draft of the stylometric and lexical scoring helpers.
- The output suggested reasonable metric groupings but did not reflect my exact thresholds or false-positive concerns.
- I overrode the raw scoring behavior by adding weighted combination rules, disagreement dampening toward `0.50`, and threshold-based label mapping from the written spec.

### Instance 3: production features and stretch routes

- I used AI to accelerate the implementation of rate limiting, appeals, certificate verification, and dashboard wiring.
- The output provided a starting structure for endpoint signatures and HTML rendering.
- I revised the behavior to match the plan exactly, especially the `under_review` appeal state, the verified-creator label prefix, and the response fields exposed for grading.

## Demo Commands

See `scripts/demo.sh` for example `curl` commands that exercise:

- `POST /submit`
- `POST /appeal`
- `GET /log`
- `POST /certificate/verify`
- `POST /submit/metadata`
- `GET /dashboard`

## Portfolio Walkthrough

For the final submission video, show:

1. a normal text submission
2. the returned label and signal scores
3. the audit log with multiple entries
4. an appeal changing status to `under_review`
5. rate limiting returning `429`
6. certificate verification and a verified label
7. the analytics dashboard

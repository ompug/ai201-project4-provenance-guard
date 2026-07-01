# Provenance Guard

**AI201 Project 4** — a Flask API that classifies creator-submitted content using multiple detection signals, returns confidence-aware transparency labels, and supports appeals with a structured audit trail.

**Repository:** [github.com/ompug/ai201-project4-provenance-guard](https://github.com/ompug/ai201-project4-provenance-guard)

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then set GROQ_API_KEY in .env
python -m flask --app app run
```

The API listens at `http://127.0.0.1:5000`. Run `bash scripts/demo.sh` for example requests.

## API endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/submit` | Text attribution (`text`, `creator_id`) |
| `POST` | `/submit/metadata` | Image description or structured metadata |
| `POST` | `/appeal` | Contest a classification (`content_id`, `creator_reasoning`) |
| `POST` | `/certificate/verify` | Earn verified-human badge |
| `GET` | `/log` | Structured audit log (JSON) |
| `GET` | `/content/<id>` | Content detail including verified badge |
| `GET` | `/dashboard` | Analytics dashboard (HTML) |
| `GET` | `/health` | Health check |

## Architecture

A submission flows through validation, three detection signals, ensemble scoring, label generation, SQLite persistence, and audit logging before the JSON response is returned.

1. **Submit** — `POST /submit` assigns a `content_id` and runs the text through all signals.
2. **Score** — weighted ensemble produces `confidence` and `attribution` (`likely_ai`, `likely_human`, or `uncertain`).
3. **Label** — plain-language transparency text is chosen from three variants.
4. **Log** — timestamp, signal scores, and verdict are written to the audit log.
5. **Appeal** — `POST /appeal` sets status to `under_review` and appends an appeal entry linked to the original decision.

See [`planning.md`](planning.md) for the full spec, thresholds, and architecture diagram.

## Detection signals

| Signal | What it measures | Blind spot |
|--------|------------------|------------|
| **Groq LLM** (`llama-3.3-70b-versatile`) | Holistic style, generic phrasing, polished "AI voice" | Formal human essays, heavily edited drafts |
| **Stylometric** | Sentence-length variance, type-token ratio, punctuation density | Poetry, dialogue, very short text |
| **Lexical formality** | Stock transition phrases (`furthermore`, `it is important to note`, etc.) | Academic and technical human writing |

Each signal returns `ai_likelihood` in `[0, 1]` (higher = more likely AI). Individual scores appear in the API response and audit log.

## Confidence scoring

**Ensemble:**

```text
combined = (groq × 0.45) + (stylometric × 0.30) + (lexical × 0.25)
```

**Disagreement dampening** (false-positive safeguard): if signal spread exceeds `0.35`, the score is pulled toward `0.50`.

**Thresholds:**

| Range | Attribution |
|-------|-------------|
| `≥ 0.72` | `likely_ai` |
| `≤ 0.38` | `likely_human` |
| otherwise | `uncertain` |

### Example submissions

**High-confidence human** (`0.324`):

```text
ugh. long day. burned toast, missed class, spilled coffee on my notes,
then laughed about it because what else was i gonna do?
```

**Lower-confidence / uncertain** (`0.423`):

```text
still thinking about that awful toast from this morning.
somehow the jam made it worse.
```

> **Note:** Without a valid `GROQ_API_KEY`, the Groq signal falls back to `0.5`, which compresses the score range. Replace `your_key_here` in `.env` with your real key for full LLM-backed detection.

## Transparency labels

| Category | Label text |
|----------|------------|
| High-confidence AI | Likely created with AI assistance. Multiple checks agree, and we are confident in this assessment. |
| Uncertain | Origin unclear. We could not confidently tell whether a person or AI wrote this. The creator can request a human review. |
| High-confidence human | Likely written by a person. Multiple checks agree, and we are confident in this assessment. |

Verified creators receive a `Verified human creator —` prefix on the label.

## Appeals, audit log, and rate limiting

**Appeals** — creators send `content_id` and `creator_reasoning`; status becomes `under_review` and a linked appeal row appears in `GET /log`.

**Audit log** — structured JSON via `GET /log`; each entry includes timestamp, attribution, confidence, individual signal scores, and status. Appeals include `appeal_reasoning`.

**Rate limiting** — `10 per minute; 100 per day` per IP on submit routes. Rationale: allows revision bursts for normal writers while blocking scripted flooding.

```text
200 × 10, then 429
```

## Stretch features

- **Ensemble detection** — three signals with documented weighting and conflict resolution
- **Provenance certificate** — `POST /certificate/verify` grants a verified-human badge when a sample scores `likely_human` at `≤ 0.38`
- **Analytics dashboard** — `GET /dashboard` shows verdict ratios, appeal rate, and average confidence
- **Multi-modal** — `POST /submit/metadata` for image descriptions and structured metadata

## Known limitations

- **Formal academic prose** may score AI-leaning because polished transitions trigger the lexical and LLM signals.
- **Repetitive poetry** can look AI-like to stylometrics due to intentionally low variance.
- **Very short submissions** lack enough structure for reliable stylometric scoring and often remain `uncertain`.

## Spec reflection

The planning spec helped most with uncertainty design — defining what `uncertain` means before coding made disagreement dampening straightforward. The main divergence was expanding to three signals (instead of two) so the ensemble stretch feature shares the same pipeline as the required multi-signal detection.

## AI usage

1. **Flask scaffold and storage** — AI drafted route layout and SQLite helpers; I separated audit logging from content persistence and standardized `content_id` handling.
2. **Scoring heuristics** — AI suggested metric groupings; I overrode thresholds, weighting, and dampening to match the written spec.
3. **Production layer** — AI accelerated appeals, rate limiting, certificate, and dashboard wiring; I aligned behavior to the plan (`under_review` state, verified label prefix, rubric-visible response fields).

## Portfolio walkthrough

Record a short (~2 min) video showing: submit → label and signals → audit log → appeal → rate limit `429` → certificate verification → dashboard.

## Project structure

```text
app.py              Flask routes and limiter
planning.md         Pre-implementation spec
signals/            Groq, stylometric, and lexical detectors
scoring.py          Ensemble combination
labels.py           Transparency label mapping
storage.py          SQLite content store and audit log
templates/          Analytics dashboard
scripts/demo.sh     curl demos for graders
```

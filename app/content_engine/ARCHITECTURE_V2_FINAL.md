# BizzBuzz Content Engine v2 — Final Architecture (Updated)

## Core Philosophy: Show, Don't Tell

The content engine teaches AI to write great posts by showing it examples of great posts — not by giving it rules. The reference library is the product.

---

## The Three Layers of a Great Post

```
Layer A: Content Type Brief          → "Here's the JOB this post does" (3 sentences, static)
Layer B: Reference Library           → "Here's what the job looks like done well" (3-10 viral/curated posts)
Layer C: Business Voice Brief        → "Here's WHO you are" (200-300 words, assembled per business)
```

**Layer A** is static — 11 content type briefs, rarely change.
**Layer B** is the living, growing part — fed by trending intelligence + human curation + performance data.
**Layer C** is per-business — assembled from MERAG, business context, instructions, team data.

---

## Data Sources

### 1. Trending Intelligence Board (Real-Time)

The trending intelligence board collects:
- **Social Pulse**: Viral posts with engagement metrics (views, likes, comments)
- **Trending Topics**: Rising topics with growth % signals
- **Industry News**: Scored news articles by relevance
- **Trending Hashtags**: Currently popular hashtags per vertical

This data serves DOUBLE DUTY:
- Stage 1 (Strategist): Trending topics + industry news = **topic inspiration** (timely content)
- Stage 2 (Writer): Viral social posts = **reference library** (style/hook examples)
  
### 2. Curation Layer (Optional Human Step)

Between trending board and content engine, humans can optionally:
- **Pin** items as "use this" in the next calendar
- **Tag** items with content type (e.g., "this is authority_opinion inspiration")
- **Tag** items as reference posts (e.g., "use this as a writing example")
- **Dismiss** irrelevant items
- **Add notes** (e.g., "angle this toward our new product launch")
- **Leave untouched** — raw trending data flows through, Strategist maps it

If human curates → engine gets richer, targeted input.
If human doesn't → raw trending data flows through and AI maps it.

### 3. Opportunity Data (From Caller/API)

Existing data the caller provides:
- Keywords + search volumes
- News items + snippets
- Audience questions
- Competitor content titles
- Business-specific content

### 4. Vertical Configuration (From DB)

Already built:
- Content type weights per vertical
- Seasonal triggers per vertical + month
- Business overrides

---

## The 3-Stage Pipeline

```
Trending Intelligence API ──┐
Curation Layer (optional) ──┤
Caller Opportunity Data ────┤
                            ▼
┌──────────────────────────────────────────────────────────────┐
│  STEP 0: ASSEMBLE CONTEXT (Code, no AI)                      │
│                                                              │
│  - Load business data → build Business Voice Brief           │
│  - Detect vertical                                           │
│  - Load vertical_config + business overrides                 │
│  - Load seasonal triggers for target months                  │
│  - Load opportunity data from caller                         │
│  - Fetch trending intelligence (social pulse, topics, news,  │
│    hashtags) for this vertical                               │
│  - Load curated picks (if any)                               │
│  - Load recent post history (dedup)                          │
│  - Parse caller instructions                                 │
│                                                              │
│  Output: One resolved context object                         │
└──────────────────────┬───────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────────┐
│  STAGE 1: STRATEGIST (1 AI call, or deep research)           │
│                                                              │
│  Job: Pick topics, assign content types, balance calendar    │
│                                                              │
│  Gets:                                                       │
│  1. Caller instructions (HIGHEST PRIORITY)                   │
│  2. Curated picks with tags (human-selected, use directly)   │
│  3. Content Type Reference Card (lightweight identity cards) │
│  4. Resolved content type weights for this business          │
│  5. Seasonal triggers active for target months               │
│  6. Opportunity data (keywords, news, questions, competitors)│
│  7. Trending topics + growth signals                         │
│  8. Industry news + relevance scores                         │
│  9. Viral social posts as topic inspiration                  │
│  10. Business summary (3-4 sentences)                        │
│  11. Recent post titles for dedup (last 90 days)             │
│  12. Number of posts needed                                  │
│                                                              │
│  Content variety guidance (taught, not assigned):            │
│  - Mix timely (news, trends, seasonal) with timeless         │
│    (evergreen, foundational advice). At least 30% each.      │
│  - Mix intents: engage vs trust vs convert                   │
│  - Mix audience stages: cold vs warm vs hot                  │
│  - Mix voices: founder, team, customer, expert, narrator     │
│  - Mix formats: story, comparison, question, statement       │
│  - No two consecutive posts same timeliness+intent+voice     │
│                                                              │
│  Outputs per topic:                                          │
│  - theme_title, content_type, target_emotion, timeliness     │
│  - hook_direction, source, source_title                      │
│  - product_focus, requires_real_photo                        │
│                                                              │
│  DEEP RESEARCH MODE (ai_provider=deep-research):             │
│  - Same prompt structure but with web search enabled         │
│  - Discovers topics caller may not have provided             │
│  - Includes pre-researched data + live web research          │
│  - Takes minutes vs seconds, produces richer context         │
│  - Stage 2 switches to Claude for writing                    │
└──────────────────────┬───────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────────┐
│  STAGE 2: WRITER (1 call per post, or batch for deep research│
│                                                              │
│  Job: Write one post that belongs in the reference collection│
│                                                              │
│  Gets (per post):                                            │
│  1. Layer A: Content Type Brief (3 sentences — the JOB)      │
│     "Authority/Opinion: Take a contrarian stance on something│
│      the industry gets wrong. Reader thinks 'I never saw it  │
│      that way.' Hook challenges a common belief."            │
│                                                              │
│  2. Layer B: Reference Posts (ALL curated + viral posts       │
│     matching this content_type + vertical + platform)        │
│     - From curated items tagged as reference posts            │
│     - From trending social pulse (viral posts)               │
│     - Waterfall: specific → vertical → universal             │
│     - Typically 5-10 posts, pass ALL of them                 │
│     "Write something that belongs in this collection"        │
│                                                              │
│  3. Business Voice Brief (assembled in Step 0)               │
│     WHO WE ARE: Smith HVAC — 12 years, family-run, 6 crew   │
│     HOW WE TALK: Blue-collar honest. No corporate polish.    │
│     WHAT MAKES US US: We answer the phone at 2am.            │
│     PROOF POINTS: 90-min response, 4.9 stars, 2200+ jobs    │
│     OUR PEOPLE: Marcus (new hire), owner does service calls  │
│                                                              │
│  4. Topic Assignment (from Stage 1)                          │
│     theme_title, hook_direction, target_emotion, product     │
│                                                              │
│  5. Trending Hashtags (for this vertical)                    │
│                                                              │
│  6. Constraints (minimal — formatting only)                  │
│     - Under X words, Y hashtags, platform format rules       │
│     - No URLs in body, no "we are proud to"                  │
│                                                              │
│  Does NOT get:                                               │
│  - Rules about hook craft (examples teach this)              │
│  - Rules about emotion (examples teach this)                 │
│  - Rules about structure (examples teach this)               │
│  - Content type training master (replaced by reference lib)  │
│                                                              │
│  BATCH MODE (deep research path):                            │
│  - All posts written in single Claude call                   │
│  - Same reference library injection                          │
│  - Faster but slightly less per-post customization           │
└──────────────────────┬───────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────────┐
│  STAGE 3: VALIDATOR (Code, no AI)                            │
│                                                              │
│  Checks:                                                     │
│  □ No two consecutive same content types (swap if found)     │
│  □ Soft promotional ≤ 20%                                    │
│  □ Origin network ≤ 2 per month                              │
│  □ Timeliness mix: at least 30% timely, 30% timeless         │
│  □ Every post has exactly one content type                   │
│  □ Real photo flags set correctly                            │
│  □ Assign publication dates + times from channel config      │
│                                                              │
│  Saves: Post titles to generated_posts (via existing API)    │
└──────────────────────┬───────────────────────────────────────┘
                       │
                       ▼
                 API Response
```

---

## Reference Library: How It Gets Populated

### Phase 1: Manual Seed (Now)
- Curate 5-10 great posts per content type from real viral content
- Use trending intelligence board's Social Pulse as primary source
- Human tags them with content_type and vertical

### Phase 2: Trending Intelligence Feed (Soon)
- Viral social posts auto-feed into reference library
- Filtered by vertical match and engagement threshold
- Human curation layer can pin/dismiss before injection

### Phase 3: Performance Flywheel (Later)
- Generated posts that perform well get flagged
- Top performers added back to reference library
- Real engagement data auto-promotes/demotes examples
- Library gets better with every calendar generated

### Reference Post Selection (Stage 2)
```
For each post to write:
  1. Query: content_type + vertical + platform (curated + viral)
  2. If < 3 results: add content_type + vertical (any platform)
  3. If < 3 results: add content_type only (universal)
  4. Pass ALL matching results (typically 5-10 posts)
  5. AI decides which examples are most relevant to the topic
```

---

## DB Schema

### Existing Tables (Already Built)
```
content_engine_vertical_config        — content type weights per vertical
content_engine_business_override      — per-business overrides
content_engine_seasonal_triggers      — seasonal triggers per vertical
```

### New Tables

```sql
-- Content type briefs (Layer A) — 11 rows, rarely changes
CREATE TABLE content_engine_type_briefs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    content_type VARCHAR(50) NOT NULL UNIQUE,
    brief_text TEXT NOT NULL,  -- 3 sentences describing the job
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Reference library (Layer B) — curated + auto-populated
CREATE TABLE content_engine_reference_library (
    id INT AUTO_INCREMENT PRIMARY KEY,
    content_type VARCHAR(50) NOT NULL,
    vertical VARCHAR(50) NULL,           -- NULL = universal
    platform VARCHAR(20) NULL,           -- NULL = all platforms
    post_text TEXT NOT NULL,             -- the actual post content
    hook_line TEXT NULL,                 -- first line extracted
    why_it_works TEXT NULL,              -- optional annotation
    source VARCHAR(50) NOT NULL,         -- 'manual_seed', 'trending_viral', 'generated_top', 'real_performance'
    source_url TEXT NULL,                -- original URL if from trending
    engagement_views INT NULL,
    engagement_likes INT NULL,
    engagement_comments INT NULL,
    performance_tier VARCHAR(20) DEFAULT 'good',  -- 'top', 'good', 'average'
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_type_vertical_platform (content_type, vertical, platform)
);

-- Curated items from trending intelligence board
CREATE TABLE content_engine_curated_items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    trending_item_id VARCHAR(100) NULL,   -- ID from trending intelligence system
    item_type VARCHAR(50) NOT NULL,       -- 'social_pulse', 'topic', 'news', 'hashtag'
    vertical VARCHAR(50) NULL,
    content TEXT NOT NULL,                -- the actual content/title
    engagement_data JSON NULL,            -- views, likes, comments, growth %
    curation_action VARCHAR(20) NOT NULL, -- 'pinned', 'dismissed', 'tagged_reference', 'tagged_topic'
    tagged_content_type VARCHAR(50) NULL, -- human-assigned content type
    notes TEXT NULL,                      -- human notes/instructions
    use_as_reference BOOLEAN DEFAULT FALSE, -- flag: inject into Stage 2 as reference post
    use_as_topic BOOLEAN DEFAULT FALSE,     -- flag: inject into Stage 1 as must-use topic
    curated_by VARCHAR(100) NULL,
    curated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    active BOOLEAN DEFAULT TRUE,
    INDEX idx_vertical_action (vertical, curation_action)
);
```

---

## API Endpoints

### Existing (Already Built)
```
POST   /strategygen/content-engine/generate
GET    /strategygen/content-engine/config/verticals
GET    /strategygen/content-engine/config/vertical/<v>
POST   /strategygen/content-engine/config/business/<id>/override
GET    /strategygen/content-engine/config/business/<id>/overrides
DELETE /strategygen/content-engine/config/business/<id>/override
GET    /strategygen/content-engine/config/seasonal-triggers
POST   /strategygen/content-engine/config/seasonal-triggers
PUT    /strategygen/content-engine/config/seasonal-triggers/<id>
DELETE /strategygen/content-engine/config/seasonal-triggers/<id>
```

### New: Reference Library Management
```
GET    /content-engine/reference-library                    — list (filter by type/vertical/platform)
POST   /content-engine/reference-library                    — add reference post
PUT    /content-engine/reference-library/<id>                — update
DELETE /content-engine/reference-library/<id>                — remove
POST   /content-engine/reference-library/import-from-trending — bulk import from trending social pulse
```

### New: Content Type Briefs
```
GET    /content-engine/type-briefs                          — list all 11
PUT    /content-engine/type-briefs/<content_type>            — update brief text
```

### New: Curation Layer
```
GET    /content-engine/curated-items                        — list curated items
POST   /content-engine/curated-items                        — pin/tag/dismiss trending item
PUT    /content-engine/curated-items/<id>                    — update curation
DELETE /content-engine/curated-items/<id>                    — remove curation
GET    /content-engine/curated-items/pending                 — items from trending not yet curated
```

---

## Business Voice Brief (Layer C)

Assembled in Step 0 from multiple sources:

```
Sources:
├── business_context (from API)         → name, industry, location, audience, USP
├── MERAG data (from DB)                → products, customers, keywords, competitors
├── caller instructions (from API)      → "we just hired Marcus", "focus on AC"
├── business_config_override (from DB)  → tone preferences
├── team data (if available)            → named people, roles, milestones

Output format (injected into Stage 2):
WHO WE ARE: [name] — [years], [size], [vibe]
HOW WE TALK: [tone description — 1 sentence]
WHAT MAKES US US: [the thing that's uniquely true — 1 sentence]
PROOF POINTS: [specific numbers, awards, metrics]
OUR PEOPLE: [named team members + one detail each]
```

---

## Content Variety (Taught, Not Assigned)

The Strategist is taught these dimensions exist but is NOT assigned values for each:

- **Timeliness**: timely (news, trends, seasonal) vs timeless (evergreen)
- **Intent**: engage vs trust vs convert
- **Audience stage**: cold vs warm vs hot
- **Voice**: founder vs team vs customer vs expert vs narrator
- **Format**: story vs comparison vs question vs statement

Only **timeliness** is tracked in output schema (for Validator to check 30/30 mix).
All others are left to AI judgment based on reference library variety.

---

## Files Affected

### Modified (from current implementation)
```
modules/content_engine/pipeline.py         — reference library injection replaces training master
modules/content_engine/routes.py           — new endpoints for reference library + curation
modules/content_engine/models.py           — new DB models
modules/content_engine/setup_db.py         — seed type briefs + initial reference posts
modules/content_engine/config_resolver.py  — add reference library resolver
```

### New Files
```
modules/content_engine/reference_resolver.py  — waterfall query logic for reference posts
modules/content_engine/voice_brief_builder.py — assembles business voice brief from multiple sources
modules/content_engine/trending_integration.py — fetches from trending intelligence API
modules/content_engine/curation_routes.py      — CRUD for curated items
```

### Kept As-Is
```
resources/prompts/strategy-gen/content-types/content_type_reference_card.txt  — still used in Stage 1
resources/prompts/strategy-gen/content-types/content_type_training_master.txt — becomes seed data, no longer injected directly
```

---

## What's NOT in This Phase
- Viral pattern engine / hooks library
- Performance tracking / feedback loop (Phase 3 of flywheel)
- Auto-import from trending intelligence (Phase 2)
- Brand Voice questionnaire integration
- Vector store integration for reference library

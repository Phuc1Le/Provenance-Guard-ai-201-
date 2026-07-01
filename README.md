# Provenance Guard

## Setup and how to run

**Requirements:** Python 3.9+, a [Groq API key](https://console.groq.com/)

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Create a `.env` file in the project root:
   ```
   GROQ_API_KEY=your_key_here
   ```

3. Start the server:
   ```bash
   python app.py
   ```
   The server runs at `http://127.0.0.1:5000`. The SQLite database (`provenance_guard.db`) is created automatically on first run.

---

## API Endpoints

### POST /submit

Submits text for AI attribution analysis.

**Request**
```json
{
    "user_id": "alice",
    "text": "Your essay or creative writing here..."
}
```

**Response**
```json
{
    "post_id": "3f7a2b1e-...",
    "label": "Likely AI",
    "transparency_message": "The writing exhibits several characteristics commonly associated with AI-generated text.",
    "confidence_score": 0.74,
    "llm_score": 0.81,
    "stylometric_score": 0.57,
    "stylometric_features": {
        "sentence_length_variation": 0.82,
        "type_token_ratio": 0.41,
        "paragraph_length_variation": 0.91,
        "longest_sentence": 0.53
    },
    "reasoning": ["...", "..."],
    "injection_detected": false,
    "status": "classified"
}
```

**Error responses**
| Status | Condition |
|--------|-----------|
| 400 | Text is too short (under 30 words) or too long (over 3,000 words) |
| 429 | User has reached their 5-submission limit |

---

### POST /appeal

Dispute a classification result. Appeals do not trigger re-classification — they flag the submission for manual review.

**Request**
```json
{
    "content_id": "3f7a2b1e-...",
    "creator_reasoning": "I wrote this myself. I am a non-native English speaker and my writing style may appear more formal than typical."
}
```

**Response**
```json
{
    "post_id": "3f7a2b1e-...",
    "status": "under_review",
    "message": "Appeal submitted successfully. Your content has been flagged for manual review."
}
```

**Error responses**
| Status | Condition |
|--------|-----------|
| 404 | `content_id` not found |
| 409 | An appeal has already been filed for this submission |

---

### GET /log

Returns all classification entries, most recent first. Entries include appeal data when an appeal has been filed.

**Response**
```json
{
    "entries": [
        {
            "post_id": "3f7a2b1e-...",
            "user_id": "alice",
            "label": "Likely AI",
            "confidence_score": 0.74,
            "llm_score": 0.81,
            "stylometric_score": 0.57,
            "reasoning": ["...", "..."],
            "status": "under_review",
            "timestamp": "2025-04-01T14:32:10.123456+00:00",
            "appeal_reasoning": "I wrote this myself...",
            "appeal_timestamp": "2025-04-01T15:10:05.654321+00:00"
        }
    ]
}
```

---

## Multi-signal detection

Provenance Guard uses two independent signals that run in parallel on every submission. Their scores are combined into a single confidence score.

### LLM signal

The text is sent to `llama-3.3-70b-versatile` via Groq with a structured system prompt that instructs the model to return a JSON object:

```json
{
    "score": 0.0,
    "reasoning": ["observation 1", "observation 2"]
}
```

The score ranges from 0.0 (definitely human) to 1.0 (definitely AI). The prompt explicitly anchors five score ranges with descriptions and lists directional signals (e.g., filler affirmations push the score up; typos and personal voice push it down), preventing the model from collapsing to binary 0.2 / 0.8 outputs.

### Stylometric heuristic signal

Four structural features are computed directly from the text without calling any external API:

| Feature | Condition | Human signal | AI signal |
|---------|-----------|-------------|-----------|
| Sentence length variation (std dev) | Always | High variation | Low variation |
| Type-token ratio | ≥ 200 words | High ratio | Low ratio |
| Paragraph length variation (variance) | ≥ 3 paragraphs | High variance | Low variance |
| Longest sentence (word count) | Always | > 30 words | < 15 words |

Each feature is normalized to a 0–1 score where 1.0 = strongly AI-like. Features that cannot be computed (e.g., too few paragraphs) are skipped; the remaining features are averaged.

### Confidence score calculation

The two signal scores are combined using a weighted average:

```
confidence = 0.65 × llm_score + 0.35 × stylometric_score
```

The LLM carries more weight (65%) because it evaluates semantic content and writing style holistically. The stylometric signal carries 35% — enough to meaningfully shift borderline cases, particularly for longer texts where all four features can be computed.

#### Examples

<!-- Fill in with real outputs from /submit -->

**Example 1 — AI-generated content**

```json
In today’s fast-paced digital landscape, artificial intelligence has become an arduous tool for businesses looking to streamline their operations. By harnessing the power of machine learning, organizations can delve into complex data sets and foster unprecedented innovation. It is important to note that while the benefits cannot be overstated, companies must carefully balance these advancements with human oversight.
```
Response:
```
HTTP/1.1 200 OK
Server: Werkzeug/3.1.8 Python/3.14.2
Date: Wed, 01 Jul 2026 06:13:38 GMT
Content-Type: application/json
Content-Length: 902
Connection: close

{
  "confidence_score": 0.7907,
  "injection_detected": false,
  "label": "Likely AI",
  "llm_score": 0.82,
  "post_id": "5a7d2c04-e5de-4bcf-b215-b419e417f7c8",
  "reasoning": [
    "The text features overly balanced phrasing, such as 'it is important to note', which is a common trait of AI-generated content",
    "The language used is polished and lacks personal voice or opinion, suggesting a more formulaic approach",
    "The inclusion of generic transitions, like 'it is important to note', further supports the likelihood of AI generation",
    "The absence of typos, colloquialisms, or emotional register also points towards AI-generated content"
  ],
  "status": "classified",
  "stylometric_features": {
    "longest_sentence": 0.6,
    "sentence_length_variation": 0.8727
  },
  "stylometric_score": 0.7364,
  "transparency_message": "Most of the evidence suggests AI-generated writing."
}
```
**Example 2 — Human-written content**

```json
He was frightened at the sight of so many gentlemen, which made him tremble: and
the beadle gave him another tap behind, which made him cry. These two causes made
him answer in a very low and hesitating voice; whereupon a gentleman in a white
waistcoat said he was a fool. Which was a capital way of raising his spirits, and putting
him quite at his ease.
```
Response:
```
HTTP/1.1 200 OK
Server: Werkzeug/3.1.8 Python/3.14.2
Date: Wed, 01 Jul 2026 06:15:36 GMT
Content-Type: application/json
Content-Length: 954
Connection: close

{
  "confidence_score": 0.3234,
  "injection_detected": false,
  "label": "Likely Human",
  "llm_score": 0.28,
  "post_id": "3d988281-d1a0-4c36-be73-f608a17af4c4",
  "reasoning": [
    "The text features a strong personal voice and opinion, as evidenced by the sarcastic tone in the last sentence",
    "The use of colloquial language and emotional register, such as 'tremble' and 'cry', adds to the human-like quality of the text",
    "The narrative is informal and conversational, with a touch of humor and irony, which are characteristic of human writing",
    "The text lacks the polished and formulaic structure often found in AI-generated content, with a more varied sentence length and rhythm"
  ],
  "status": "classified",
  "stylometric_features": {
    "longest_sentence": 0.2667,
    "sentence_length_variation": 0.541
  },
  "stylometric_score": 0.4039,
  "transparency_message": "This content is likely to have been written by a human."
}
```
---

## Transparency label

The confidence score is mapped to one of five labels using asymmetric thresholds. The thresholds are intentionally harder to cross toward the AI end, minimising false positives (incorrectly labelling human writing as AI-generated).

| Confidence score | Label |
|-----------------|-------|
| 0.00 – 0.15 | Definitely Human |
| 0.15 – 0.35 | Likely Human |
| 0.35 – 0.65 | Uncertain |
| 0.65 – 0.90 | Likely AI |
| 0.90 – 1.00 | Definitely AI |

Each label has four possible display messages that are chosen at random
### Definitely Human

Possible messages:

- Our analysis found strong evidence that this content was written by a human.
- This content exhibits characteristics strongly associated with human writing.
- We found little evidence suggesting this content was AI-generated.
- Based on our analysis, this content is almost certainly human-written.

---

### Likely Human

Possible messages:

- This content is likely to have been written by a human.
- Most of the evidence suggests human authorship.
- The writing appears predominantly human, although some AI-like characteristics were detected.
- Our analysis leans toward this content being human-written.

---

### Uncertain

Possible messages:

- Our analysis found mixed signals and could not confidently determine the origin of this content.
- This content contains characteristics of both human and AI writing.
- The available evidence is inconclusive.
- We cannot confidently determine whether this content was written by a person or generated by AI.

---

### Likely AI

Possible messages:

- This content is likely to have been generated by AI.
- Most of the evidence suggests AI-generated writing.
- The writing exhibits several characteristics commonly associated with AI-generated text.
- Our analysis leans toward this content being AI-generated.

---

### Definitely AI

Possible messages:

- Our analysis found strong evidence that this content was generated by AI.
- This content appears to be AI-generated with high confidence.
- The writing exhibits multiple characteristics strongly associated with AI-generated text.
- Based on our analysis, this content is almost certainly AI-generated.

---
The system tends to return **Uncertain** when the two signals disagree significantly — their weighted average naturally falls in the 0.35–0.65 range when one signal pulls toward human and the other toward AI. It also occurs when the text is short or when the writing style is naturally formal (e.g. technical documentation).

---

## Rate limiting

Each user is allowed **5 classification submissions per day**. The count and the date of the last request are stored in the `users` table (`requests_made`, `last_request_at`). On each `/submit` call the system checks whether the last request was made on a previous calendar day — if so, the counter resets to zero before checking the limit.

Once the daily limit is reached, the endpoint returns HTTP 429 with `{"error": "Limit reached"}`.

This limit is deliberately low for demonstration purposes — it is sufficient to test all label variants and the appeal workflow without requiring a larger dataset.

Appeals do **not** count toward this limit.

---

## Audit log

Every classification is written to the `classifications` table in SQLite immediately after the signals run. The log captures:

| Field | Description |
|-------|-------------|
| `post_id` | Unique ID for the submission (UUID) |
| `user_id` | Submitting user |
| `content` | Full text of the submission |
| `confidence_score` | Combined weighted score (0–1) |
| `llm_score` | Raw score from the LLM signal |
| `stylometric_score` | Raw score from the stylometric signal |
| `label` | Transparency label |
| `reasoning` | LLM reasoning observations (JSON array) |
| `status` | `classified` or `under_review` |
| `timestamp` | UTC timestamp of submission |
| `appeal_reasoning` | Populated when an appeal is filed (via LEFT JOIN with `appeals`) |
| `appeal_timestamp` | UTC timestamp of appeal |

Sample log entries from `GET /log`:

<!-- Paste output from GET /log after generating at least 3 entries -->

```json
{
  "entries": [
    {
      "appeal_reasoning": "I asked an AI to write this",
      "appeal_timestamp": "2026-07-01T06:26:51.802830+00:00",
      "confidence_score": 0.2942,
      "content": "Dear Professor, I hope you are doing well. I am writing to let you know that I am feeling unwell and would like to request permission to take the day off from class today so that I can rest and recover. I apologize for any inconvenience this may cause. I will make sure to catch up on any material or assignments I miss during my absence. Thank you for your understanding. I appreciate your consideration and hope to return to class as soon as I am feeling better. Sincerely, Phuc",
      "label": "Likely Human",
      "llm_score": 0.42,
      "post_id": "bf5cbb6d-8059-4a68-8f21-346b2a121bf7",
      "reasoning": [
        "The text is a straightforward, polite request, which could be generated by either a human or an AI, but the lack of overly formal or generic transitions suggests a human touch",
        "The apology for inconvenience and the promise to catch up on missed material are phrases that could be used by either humans or AI, but the overall tone is somewhat personal and considerate",
        "There are no noticeable typos, colloquialisms, or strong personal opinions, which might suggest a more polished, AI-generated text, but the language is not overly complex or formulaic",
        "The closing sentence, expressing appreciation and hope to return to class, has a somewhat personal tone, which leans slightly towards human authorship"
      ],
      "status": "under_review",
      "stylometric_score": 0.0607,
      "timestamp": "2026-07-01T06:24:43.932500+00:00",
      "user_id": "phuc"
    },
    {
      "appeal_reasoning": null,
      "appeal_timestamp": null,
      "confidence_score": 0.3234,
      "content": "Oliver was frightened at the sight of so many gentlemen, which made him tremble: and the beadle gave him another tap behind, which made him cry. These two causes made him answer in a very low and hesitating voice; whereupon a gentleman in a white waistcoat said he was a fool. Which was a capital way of raising his spirits, and putting him quite at his ease.",
      "label": "Likely Human",
      "llm_score": 0.28,
      "post_id": "3f9ba6bc-8054-48e5-be12-17295ab6caf9",
      "reasoning": [
        "The text features a strong personal voice and opinion, as evidenced by the sarcastic tone in the last sentence.",
        "The use of colloquial language, such as 'made him cry' and 'putting him quite at his ease', suggests a human touch.",
        "The narrative has a clear emotional register that varies within the text, from fear to sarcasm, which is a characteristic of human writing.",
        "The text's tone and language are reminiscent of classic literature, such as Charles Dickens, which further supports the likelihood of human authorship."
      ],
      "status": "classified",
      "stylometric_score": 0.4039,
      "timestamp": "2026-07-01T06:16:10.001518+00:00",
      "user_id": "alice"
    },
    {
      "appeal_reasoning": null,
      "appeal_timestamp": null,
      "confidence_score": 0.3234,
      "content": "He was frightened at the sight of so many gentlemen, which made him tremble: and the beadle gave him another tap behind, which made him cry. These two causes made him answer in a very low and hesitating voice; whereupon a gentleman in a white waistcoat said he was a fool. Which was a capital way of raising his spirits, and putting him quite at his ease.",
      "label": "Likely Human",
      "llm_score": 0.28,
      "post_id": "3d988281-d1a0-4c36-be73-f608a17af4c4",
      "reasoning": [
        "The text features a strong personal voice and opinion, as evidenced by the sarcastic tone in the last sentence",
        "The use of colloquial language and emotional register, such as 'tremble' and 'cry', adds to the human-like quality of the text",
        "The narrative is informal and conversational, with a touch of humor and irony, which are characteristic of human writing",
        "The text lacks the polished and formulaic structure often found in AI-generated content, with a more varied sentence length and rhythm"
      ],
      "status": "classified",
      "stylometric_score": 0.4039,
      "timestamp": "2026-07-01T06:15:36.567836+00:00",
      "user_id": "alice"
    },
    {
      "appeal_reasoning": null,
      "appeal_timestamp": null,
      "confidence_score": 0.6057,
      "content": "A small bookstore sat at the corner of a quiet street, its windows glowing warmly as rain tapped against the glass. Inside, visitors wandered slowly through the shelves, pausing to read the backs of worn novels and discover unexpected treasures. The scent of old paper and fresh coffee filled the air, making it easy to lose track of time. By the time the storm had passed, several people left carrying books they hadn't planned to buy but were already excited to read.",
      "label": "Uncertain",
      "llm_score": 0.58,
      "post_id": "cddd1f48-1cb4-44bb-99ad-8e8eb74d81eb",
      "reasoning": [
        "The text features descriptive language and sensory details, which could be indicative of either human or AI writing.",
        "The structure and pacing of the passage are well-balanced and polished, suggesting a possible AI influence.",
        "However, the use of vivid and specific imagery, such as 'rain tapped against the glass' and 'the scent of old paper and fresh coffee', introduces a touch of human-like creativity and emotional resonance.",
        "The narrative also lacks overtly formulaic transitions or generic phrasing, which prevents the score from leaning further towards AI-generated content."
      ],
      "status": "classified",
      "stylometric_score": 0.6535,
      "timestamp": "2026-07-01T06:12:42.463903+00:00",
      "user_id": "alice"
    }
  ]
}
```

---

## AI Usage

### Milestone 3
I design the endpoints, their request and response format myself. I also defined the database schemas. I asked ChatGPT (since I was out of Claude credits) to help me write the Flask API and database logging. Then, I did some copy-pasting and test the endpoints.
### Milestone 4
Claude is back. I discussed with it about the parameters in the stylometric heuristic, made it clear that my goals is to classify long text-based content like essays, creative writings, not short blogs, comments. After agreeing on the parameters, I asked Claude to write the standalone stylometric.py. I did some testing and modified the code. 
### Milestone 5
Then, Claude wired both signals into app.py, implementing guardrails and injection check based on the planning.md that I wrote by myself. I didn't know what Flask-limiter was before, so my strategy for rate limiting is using a different table. Claude agreed with that and help me implement that feature.

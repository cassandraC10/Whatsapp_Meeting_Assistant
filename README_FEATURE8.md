# TCA V0.5 Feature 8 — Conversation Feedback

## What changed

Feature 8 adds lightweight post-processing feedback to completed conversations.

Users can submit:

- **Helpful**
- **Needs work**
- optional free-text feedback

Feedback is attached to the authenticated user and conversation. The backend
stores the current feedback state and also records an append-only product event.

This is intentionally structured so Feature 9 Analytics can consume the same
event stream instead of introducing a second feedback/analytics pipeline.

## Feedback data model

### Current feedback

`conversation_feedback` stores one current feedback record per:

```text
user_id + call_id
```

A user can update their feedback later without creating duplicate current-state
records.

Fields:

- `id`
- `user_id`
- `call_id`
- `rating`
- `comment`
- `created_at`
- `updated_at`

### Product events

`product_events` is the shared append-only event foundation for Feature 9.

Feature 8 records:

- `feedback_submitted`
- `feedback_updated`

Each event includes:

- `user_id`
- `call_id`
- `occurred_at`
- `event_name`
- `properties`
- `source`

Feedback comments are deliberately **not** copied into event properties. This
keeps the analytics/event layer focused on product behaviour while the actual
feedback text remains in the feedback record.

The same event store can later receive:

- `sign_up`
- `login`
- `onboarding_completed`
- `capture_opened`
- `recording_started`
- `recording_finished`
- `processing_started`
- `processing_completed`
- `processing_failed`
- `conversation_saved`
- `feedback_submitted`

without changing the Feature 8 feedback architecture.

## API

### Get current feedback

```text
GET /calls/{call_id}/feedback
```

Returns the current feedback or `null`.

### Submit/update feedback

```text
POST /calls/{call_id}/feedback
```

Body:

```json
{
  "rating": "helpful",
  "comment": "The summary was clear."
}
```

`rating` must be one of:

```text
helpful
needs_work
```

Comment is optional and limited to 2000 characters.

All feedback routes require authentication and enforce conversation ownership
through the existing `require_call(...)` guard.

## Cloud

Added:

```text
backend/migrations/003_feedback_analytics_foundation.sql
```

When cloud PostgreSQL is enabled, Feature 8 mirrors:

- current feedback → `tca_feedback`
- product events → `tca_product_events`

Local SQLite remains the development fallback. Cloud mirroring is best-effort
so a temporary cloud problem does not make a user lose beta feedback locally.

## Complete files

Replace/add these files from this package:

- `backend/app/models.py`
- `backend/app/main.py`
- `backend/app/cloud.py`
- `backend/app/event_store.py`
- `backend/app/feedback.py`
- `backend/migrations/003_feedback_analytics_foundation.sql`
- `frontend/src/api.ts`
- `frontend/src/App.tsx`
- `frontend/src/styles.css`
- `frontend/src/components/ConversationFeedback.tsx`
- `tests/feedback_smoke.py`

## Local E2E

1. Start FastAPI.
2. Start Vite.
3. Log into TCA.
4. Open a completed conversation.
5. Scroll to **Feedback**.
6. Select **Helpful** or **Needs work**.
7. Optionally enter a short comment.
8. Click **Send feedback**.
9. Confirm the success message.
10. Refresh/open the same conversation.
11. Confirm the selected feedback and comment are still present.
12. Change the rating/comment.
13. Click **Update feedback**.
14. Confirm the new values persist.
15. Switch to another account.
16. Open the same conversation if it is not owned by that account — it must
    remain inaccessible.
17. Confirm another account cannot submit feedback against the first account's
    conversation.

## Smoke test

From the project root:

```powershell
python tests/feedback_smoke.py
```

Expected:

```text
Feedback smoke test passed.
```

## Frontend build

```powershell
cd frontend
npm run build
```

## Feature 8 lock

Do not lock Feature 8 until:

- feedback appears only on completed conversations
- helpful feedback saves
- needs-work feedback saves
- optional comment saves
- refresh preserves feedback
- update works
- empty comment works
- over-2000-character feedback is rejected
- account ownership is enforced
- `feedback_submitted` appears in product events
- changing feedback creates `feedback_updated`
- repeated identical submission does not create a duplicate event
- Feature 7 authenticated capture remains intact

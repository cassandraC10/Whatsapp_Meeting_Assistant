# TCA V0.5 — Feature 9: Analytics

Feature 9 adds a privacy-conscious analytics foundation on top of the Feature 8 product-event stream.

## What is included

### Product events
The append-only `product_events` stream now captures key beta behaviour:

- `sign_up`
- `login`
- `onboarding_completed`
- `capture_opened`
- `conversation_created`
- `recording_started`
- `recording_finished`
- `processing_started`
- `processing_completed`
- `processing_failed`
- `conversation_saved`
- `search_used`
- `ask_tca_used`
- `follow_up_generated`
- `feedback_submitted`
- `feedback_updated`

Events are scoped to the authenticated user and optional conversation.

### AI usage
TCA records Gemini usage metadata when the provider returns usage information:

- model
- operation
- input tokens
- output tokens
- total tokens
- cached tokens when available
- thinking tokens when available
- latency
- estimated cost when pricing is configured

The implementation reads Gemini response `usage_metadata`; it does not expose the API key or provider secrets to the frontend.

### Analytics API

- `GET /analytics?days=30` — current user's analytics
- `GET /analytics/admin?days=30` — aggregate beta analytics, only when `TCA_ANALYTICS_ADMIN_EMAIL` matches the authenticated account

### Analytics UI
The authenticated app now has an **Analytics** navigation entry with:

- usage summary
- processing success rate
- feedback helpful rate
- Gemini token/request usage
- estimated AI cost when configured
- event counts

## Gemini cost configuration

TCA deliberately keeps provider pricing configurable instead of hard-coding a permanent price into the product.

Set these backend environment variables when you want cost estimates:

```text
TCA_GEMINI_INPUT_COST_USD_PER_1M=
TCA_GEMINI_OUTPUT_COST_USD_PER_1M=
```

For a free beta, you can leave them blank and use token counts as the usage meter. If you want an internal paid-rate estimate, set the values to the current provider pricing for the model you are using.

## Admin analytics

Set:

```text
TCA_ANALYTICS_ADMIN_EMAIL=your-beta-admin@example.com
```

Only that authenticated email can call `/analytics/admin`.

## Cloud

Feature 9 adds migration `004_analytics_usage.sql` for:

- `tca_ai_usage`

Product events are already mirrored into `tca_product_events` by the Feature 8 event store foundation. AI usage is mirrored into `tca_ai_usage` when cloud mode is enabled and the database is configured.

## Local validation

```powershell
python tests\feedback_smoke.py
python tests\analytics_smoke.py
```

Frontend:

```powershell
cd frontend
npm run build
```

The build should be run on the normal Windows development machine because the packaged development dependencies can contain platform-specific Vite/Rolldown binaries.

## E2E acceptance

1. Start backend.
2. Start frontend.
3. Sign in.
4. Open **Analytics**.
5. Verify the dashboard loads.
6. Confirm a period can be changed between 7 / 30 / 90 days.
7. Open a conversation and use existing TCA features.
8. Return to Analytics and refresh.
9. Confirm product event counts change appropriately.
10. Submit/update Feature 8 feedback and confirm feedback metrics update.
11. Run `python tests\analytics_smoke.py`.
12. Run `npm run build`.
13. Only then lock and commit Feature 9.

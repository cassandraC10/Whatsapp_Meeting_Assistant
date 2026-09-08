import json
import re
import time

from google.genai import types
from pydantic import (
    BaseModel,
    Field,
)

from backend.app.models import (
    AskSource,
    AskTCAResponse,
    Call,
    CallStatus,
)

from backend.app.repository import (
    CallRepository,
)

from intelligence.summarizer import (
    MODEL_NAME,
    client,
    is_daily_quota_error,
    is_temporary_gemini_error,
)


MAX_ASK_RETRIES = 3
ASK_RETRY_DELAYS = [
    2,
    4,
]


class GroundedAnswer(
    BaseModel
):
    found_answer: bool = Field(
        description=(
            "True only when the provided "
            "conversation evidence supports "
            "an answer."
        )
    )

    answer: str = Field(
        description=(
            "A concise answer grounded only "
            "in the supplied conversations."
        )
    )

    source_call_ids: list[str] = Field(
        default_factory=list,
        description=(
            "IDs of only the conversations "
            "that directly support the answer."
        ),
    )


class AskTCAService:
    def __init__(
        self,
        repository: CallRepository,
    ):
        self.repository = repository

    def ask(
        self,
        question: str,
        call_id: str | None = None,
    ) -> AskTCAResponse:
        clean_question = (
            question.strip()
        )

        if not clean_question:
            raise RuntimeError(
                "A question is required."
            )

        if call_id:
            candidates = (
                self._get_single_call_context(
                    call_id
                )
            )

        else:
            candidates = (
                self._retrieve_context(
                    clean_question
                )
            )

        if not candidates:
            return AskTCAResponse(
                answer=(
                    "I couldn't find that in "
                    "your saved conversations."
                ),
                sources=[],
                found_answer=False,
            )

        prompt = (
            self._build_prompt(
                question=clean_question,
                candidates=candidates,
            )
        )

        response = (
            self._generate_answer(
                prompt
            )
        )

        if (
            not response.found_answer
        ):
            return AskTCAResponse(
                answer=(
                    "I couldn't find that in "
                    "your saved conversations."
                ),
                sources=[],
                found_answer=False,
            )

        valid_ids = {
            item["call"].id
            for item in candidates
        }

        source_ids = [
            source_id
            for source_id
            in response.source_call_ids
            if source_id in valid_ids
        ]

        sources = (
            self._build_sources(
                source_ids=source_ids,
                candidates=candidates,
            )
        )

        if not sources:
            return AskTCAResponse(
                answer=(
                    "I couldn't find enough "
                    "evidence in your saved "
                    "conversations to answer "
                    "that confidently."
                ),
                sources=[],
                found_answer=False,
            )

        return AskTCAResponse(
            answer=response.answer.strip(),
            sources=sources,
            found_answer=True,
        )

    def _retrieve_context(
        self,
        question: str,
    ) -> list[dict]:
        search_terms = (
            self._extract_search_terms(
                question
            )
        )

        found: dict[
            str,
            dict,
        ] = {}

        for term in search_terms:
            results = (
                self.repository.search(
                    term
                )
            )

            for result in results:
                call = result[
                    "call"
                ]

                if (
                    call.status
                    != CallStatus.COMPLETED
                ):
                    continue

                current = (
                    found.get(
                        call.id
                    )
                )

                if current is None:
                    found[
                        call.id
                    ] = {
                        "call": call,
                        "search_snippets": [],
                        "match_count": 0,
                    }

                    current = (
                        found[
                            call.id
                        ]
                    )

                snippet = (
                    result.get(
                        "snippet"
                    )
                )

                if (
                    snippet
                    and snippet
                    not in current[
                        "search_snippets"
                    ]
                ):
                    current[
                        "search_snippets"
                    ].append(
                        snippet
                    )

                current[
                    "match_count"
                ] += 1

        ranked = sorted(
            found.values(),
            key=lambda item: (
                item[
                    "match_count"
                ],
                item[
                    "call"
                ].created_at,
            ),
            reverse=True,
        )

        candidates = []

        for item in ranked[
            :5
        ]:
            context = (
                self._load_call_context(
                    item["call"]
                )
            )

            if context:
                context[
                    "search_snippets"
                ] = item[
                    "search_snippets"
                ]

                candidates.append(
                    context
                )

        return candidates

    def _get_single_call_context(
        self,
        call_id: str,
    ) -> list[dict]:
        call = (
            self.repository.get(
                call_id
            )
        )

        if call is None:
            raise RuntimeError(
                "Call not found."
            )

        if (
            call.status
            != CallStatus.COMPLETED
        ):
            raise RuntimeError(
                "Ask TCA is only available "
                "for completed conversations."
            )

        context = (
            self._load_call_context(
                call
            )
        )

        if not context:
            return []

        return [
            context
        ]

    def _extract_search_terms(
        self,
        question: str,
    ) -> list[str]:
        words = re.findall(
            r"[A-Za-z0-9']+",
            question,
        )

        stop_words = {
            "a",
            "about",
            "all",
            "an",
            "and",
            "are",
            "at",
            "be",
            "did",
            "do",
            "does",
            "for",
            "from",
            "had",
            "has",
            "have",
            "he",
            "her",
            "him",
            "his",
            "how",
            "i",
            "in",
            "is",
            "it",
            "me",
            "my",
            "of",
            "on",
            "our",
            "say",
            "said",
            "she",
            "tell",
            "that",
            "the",
            "their",
            "them",
            "there",
            "they",
            "this",
            "to",
            "was",
            "we",
            "were",
            "what",
            "when",
            "where",
            "which",
            "who",
            "why",
            "with",
            "you",
            "your",
        }

        terms = []

        for word in words:
            clean = (
                word.strip()
            )

            if len(clean) < 2:
                continue

            if (
                clean.casefold()
                in stop_words
            ):
                continue

            if clean not in terms:
                terms.append(
                    clean
                )

        full_question = (
            question.strip()
        )

        if (
            full_question
            and full_question
            not in terms
        ):
            terms.append(
                full_question
            )

        return terms[
            :8
        ]

    def _load_call_context(
        self,
        call: Call,
    ) -> dict | None:
        call_directory = (
            self.repository
            .get_directory(
                call.id
            )
        )

        notes_file = (
            call_directory
            / "notes.json"
        )

        transcript_file = (
            call_directory
            / "combined_transcript.txt"
        )

        notes = {}

        if notes_file.exists():
            try:
                notes = json.loads(
                    notes_file.read_text(
                        encoding="utf-8"
                    )
                )

            except (
                json.JSONDecodeError,
                OSError,
            ):
                notes = {}

        transcript = ""

        if transcript_file.exists():
            try:
                transcript = (
                    transcript_file
                    .read_text(
                        encoding="utf-8"
                    )
                    .strip()
                )

            except OSError:
                transcript = ""

        if (
            not notes
            and not transcript
        ):
            return None

        return {
            "call": call,
            "notes": notes,
            "transcript": transcript,
            "search_snippets": [],
        }

    def _build_prompt(
        self,
        question: str,
        candidates: list[dict],
    ) -> str:
        conversations = []

        for (
            index,
            item,
        ) in enumerate(
            candidates,
            start=1,
        ):
            call = item[
                "call"
            ]

            notes = item.get(
                "notes",
                {},
            )

            transcript = item.get(
                "transcript",
                "",
            )

            transcript_excerpt = (
                transcript[
                    :8000
                ]
            )

            conversation = f"""
CONVERSATION {index}

CALL_ID:
{call.id}

TITLE:
{call.title}

DATE:
{call.created_at.isoformat()}

SUMMARY:
{notes.get("summary", "")}

KEY POINTS:
{json.dumps(
    notes.get(
        "key_points",
        [],
    ),
    ensure_ascii=False,
)}

DECISIONS:
{json.dumps(
    notes.get(
        "decisions",
        [],
    ),
    ensure_ascii=False,
)}

MY NEXT STEPS:
{json.dumps(
    notes.get(
        "my_action_items",
        [],
    ),
    ensure_ascii=False,
)}

THEIR NEXT STEPS:
{json.dumps(
    notes.get(
        "their_action_items",
        [],
    ),
    ensure_ascii=False,
)}

IMPORTANT DATES:
{json.dumps(
    notes.get(
        "important_dates",
        [],
    ),
    ensure_ascii=False,
)}

FOLLOW-UP:
{notes.get("follow_up", "")}

TRANSCRIPT:
{transcript_excerpt}
"""

            conversations.append(
                conversation.strip()
            )

        joined_context = (
            "\n\n"
            .join(
                conversations
            )
        )

        return f"""
You are TCA, The Call Assistant.

Answer a user's question using ONLY the saved
conversation evidence provided below.

STRICT RULES:

- Do not use outside knowledge.
- Do not invent memories, people, commitments,
  dates, decisions or opinions.
- If the evidence does not clearly support an
  answer, set found_answer to false.
- When found_answer is false, do not guess.
- Use source_call_ids only for conversations
  that directly support the answer.
- Never cite a call ID that was not provided.
- Prefer concise, natural language.
- Preserve names, dates, amounts and ownership
  of actions accurately.
- Distinguish what the user said from what the
  other participant said.
- Do not treat generated summaries as stronger
  evidence than the transcript when they conflict.
- If multiple conversations are relevant, combine
  them carefully and cite all supporting calls.

USER QUESTION:

{question}


SAVED CONVERSATIONS:

{joined_context}
""".strip()

    def _generate_answer(
        self,
        prompt: str,
    ) -> GroundedAnswer:
        config = (
            types.GenerateContentConfig(
                response_mime_type=(
                    "application/json"
                ),
                response_schema=(
                    GroundedAnswer
                ),
            )
        )

        last_error = None

        for attempt in range(
            1,
            MAX_ASK_RETRIES + 1,
        ):
            try:
                print(
                    "Ask TCA attempt "
                    f"{attempt}/"
                    f"{MAX_ASK_RETRIES}..."
                )

                response = (
                    client.models
                    .generate_content(
                        model=MODEL_NAME,
                        contents=prompt,
                        config=config,
                    )
                )

                if not response.text:
                    raise RuntimeError(
                        "Ask TCA returned "
                        "an empty response."
                    )

                return (
                    GroundedAnswer
                    .model_validate_json(
                        response.text
                    )
                )

            except Exception as error:
                last_error = error

                if is_daily_quota_error(
                    error
                ):
                    raise RuntimeError(
                        "Daily Gemini quota "
                        "reached. Your saved "
                        "conversations are safe. "
                        "Try again after the "
                        "quota resets."
                    ) from error

                if not (
                    is_temporary_gemini_error(
                        error
                    )
                ):
                    raise

                if (
                    attempt
                    >= MAX_ASK_RETRIES
                ):
                    break

                delay = (
                    ASK_RETRY_DELAYS[
                        attempt - 1
                    ]
                )

                print(
                    "Ask TCA is temporarily "
                    "busy. Trying again in "
                    f"{delay} seconds..."
                )

                time.sleep(
                    delay
                )

        raise RuntimeError(
            "Ask TCA could not answer "
            "after several attempts. "
            f"Last error: {last_error}"
        )

    def _build_sources(
        self,
        source_ids: list[str],
        candidates: list[dict],
    ) -> list[AskSource]:
        candidate_map = {
            item[
                "call"
            ].id: item
            for item in candidates
        }

        sources = []

        for source_id in source_ids:
            item = (
                candidate_map.get(
                    source_id
                )
            )

            if not item:
                continue

            call = item[
                "call"
            ]

            snippets = item.get(
                "search_snippets",
                [],
            )

            snippet = (
                snippets[0]
                if snippets
                else None
            )

            sources.append(
                AskSource(
                    call_id=call.id,
                    title=call.title,
                    created_at=(
                        call.created_at
                    ),
                    snippet=snippet,
                )
            )

        return sources
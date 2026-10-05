import { useEffect, useState } from "react";

import {
  getCallFeedback,
  submitCallFeedback,
} from "../api";
import type {
  FeedbackRating,
} from "../api";

type ConversationFeedbackProps = {
  callId: string;
};

export function ConversationFeedback({
  callId,
}: ConversationFeedbackProps) {
  const [rating, setRating] =
    useState<FeedbackRating | null>(null);
  const [comment, setComment] =
    useState("");
  const [loading, setLoading] =
    useState(true);
  const [saving, setSaving] =
    useState(false);
  const [error, setError] =
    useState("");
  const [saved, setSaved] =
    useState(false);
  const [hasExistingFeedback, setHasExistingFeedback] =
    useState(false);

  useEffect(() => {
    let active = true;

    setLoading(true);
    setError("");
    setSaved(false);
    setRating(null);
    setComment("");
    setHasExistingFeedback(false);

    void getCallFeedback(callId)
      .then((feedback) => {
        if (!active) {
          return;
        }

        if (feedback) {
          setRating(feedback.rating);
          setComment(feedback.comment || "");
          setHasExistingFeedback(true);
        }
      })
      .catch((requestError) => {
        if (!active) {
          return;
        }

        setError(
          requestError instanceof Error
            ? requestError.message
            : "Could not load feedback.",
        );
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [callId]);

  function chooseRating(
    nextRating: FeedbackRating,
  ) {
    if (saving) {
      return;
    }

    setRating(nextRating);
    setSaved(false);
    setError("");
  }

  async function submit() {
    if (!rating || saving) {
      return;
    }

    setSaving(true);
    setError("");
    setSaved(false);

    try {
      await submitCallFeedback(
        callId,
        {
          rating,
          comment: comment.trim() || null,
        },
      );

      setHasExistingFeedback(true);
      setSaved(true);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Could not save your feedback.",
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <section
      className="recap-section conversation-feedback"
      aria-labelledby="conversation-feedback-title"
    >
      <div className="conversation-feedback-copy">
        <span className="section-label">
          Feedback
        </span>

        <h2 id="conversation-feedback-title">
          Was this conversation memory useful?
        </h2>

        <p>
          Your feedback helps us make TCA better during the private beta.
        </p>
      </div>

      {loading ? (
        <p className="feedback-loading">
          Loading feedback…
        </p>
      ) : (
        <>
          <div
            className="feedback-rating-row"
            role="group"
            aria-label="Conversation feedback rating"
          >
            <button
              type="button"
              className={
                `feedback-rating-button ${
                  rating === "helpful"
                    ? "selected"
                    : ""
                }`
              }
              onClick={() =>
                chooseRating("helpful")
              }
              disabled={saving}
              aria-pressed={
                rating === "helpful"
              }
            >
              <span aria-hidden="true">
                👍
              </span>
              Helpful
            </button>

            <button
              type="button"
              className={
                `feedback-rating-button ${
                  rating === "needs_work"
                    ? "selected"
                    : ""
                }`
              }
              onClick={() =>
                chooseRating("needs_work")
              }
              disabled={saving}
              aria-pressed={
                rating === "needs_work"
              }
            >
              <span aria-hidden="true">
                👎
              </span>
              Needs work
            </button>
          </div>

          {rating && (
            <div className="feedback-form">
              <label
                className="feedback-comment-label"
                htmlFor="conversation-feedback-comment"
              >
                <span>
                  Anything TCA should have done better?
                </span>
                <small>
                  Optional
                </small>
              </label>

              <textarea
                id="conversation-feedback-comment"
                value={comment}
                onChange={(event) =>
                  setComment(
                    event.target.value.slice(
                      0,
                      2000,
                    ),
                  )
                }
                maxLength={2000}
                placeholder="Tell us what was missing, unclear, or especially useful."
                disabled={saving}
              />

              <div className="feedback-submit-row">
                <span className="feedback-character-count">
                  {comment.length}/2000
                </span>

                <button
                  type="button"
                  className="action-button primary-action"
                  onClick={() => void submit()}
                  disabled={saving}
                >
                  {saving
                    ? "Saving…"
                    : hasExistingFeedback
                      ? "Update feedback"
                      : "Send feedback"}
                </button>
              </div>
            </div>
          )}

          {saved && (
            <p
              className="feedback-success"
              role="status"
            >
              Thanks — your feedback was saved.
            </p>
          )}

          {error && (
            <div
              className="notice notice-error feedback-error"
              role="alert"
            >
              <strong>
                Could not save feedback.
              </strong>

              <p>
                {error}
              </p>
            </div>
          )}
        </>
      )}
    </section>
  );
}

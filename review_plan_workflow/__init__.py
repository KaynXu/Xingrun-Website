"""Lightweight review-plan workflow package.

This package is intentionally small: code owns orchestration, schemas, trace
metadata, and quality gates; the LLM remains a content generator.
"""

from .service import generate_single_lesson_review_plan

__all__ = ["generate_single_lesson_review_plan"]

from __future__ import annotations

import inspect
import json
import logging
import re
import uuid
from dataclasses import dataclass
from typing import Annotated, Dict, List, Literal, Mapping, Optional, Tuple, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

import config_runtime


logger = logging.getLogger(__name__)

MemoryType = Literal["teacher_style", "student_fact"]
SupportText = Annotated[str, Field(min_length=1, max_length=500)]


def _prepare_local_bm25_encoder(client: object) -> None:
    vector_store = getattr(client, "vector_store", None)
    if vector_store is None or not bool(
        getattr(vector_store, "_has_bm25_slot", False)
    ):
        return
    try:
        from fastembed import SparseTextEmbedding

        vector_store._bm25_encoder = SparseTextEmbedding(
            model_name="Qdrant/bm25",
            local_files_only=True,
        )
    except Exception as exc:
        # Request handling must never wait for a model download. Mem0 already
        # treats this sentinel as semantic-only search when BM25 is unavailable.
        vector_store._bm25_encoder = False
        logger.warning(
            "Local BM25 encoder unavailable; using semantic-only memory search: %s",
            type(exc).__name__,
        )


def _attach_timed_qdrant_client(
    vector_config: Dict[str, object],
    qdrant_url: str,
    qdrant_api_key: str,
    timeout_seconds: int,
) -> None:
    """Pass a project-built Qdrant client so vector calls carry a timeout.

    mem0 2.x builds ``QdrantClient(url=..., api_key=...)`` with no timeout, and
    its config validator rejects a bare URL without an api key (it requires
    url+api_key, host+port, or path). Building the client here with an explicit
    timeout keeps the self-hosted keyless deployment working; the client field
    takes precedence inside mem0, and host/port only satisfy the validator.
    """
    try:
        from qdrant_client import QdrantClient
        from urllib.parse import urlsplit

        parsed = urlsplit(qdrant_url)
        host = parsed.hostname
        if not host:
            raise ValueError("qdrant url has no hostname")
        kwargs: Dict[str, object] = {"url": qdrant_url, "timeout": timeout_seconds}
        if qdrant_api_key:
            kwargs["api_key"] = qdrant_api_key
        vector_config["client"] = QdrantClient(**kwargs)
        if not qdrant_api_key:
            vector_config["host"] = host
            vector_config["port"] = int(parsed.port or 6333)
    except Exception as exc:
        logger.warning(
            "falling back to a mem0-managed Qdrant client without timeout: %s",
            type(exc).__name__,
        )


def _apply_openai_http_timeouts(memory: object, timeout_seconds: int) -> None:
    """mem0 2.x builds its OpenAI clients without a timeout (600s default);
    replace them with identically configured clients that fail fast upstream."""
    try:
        import httpx
        from openai import OpenAI
    except ImportError:
        return
    request_timeout = httpx.Timeout(
        timeout_seconds, connect=min(10.0, float(timeout_seconds))
    )
    for attribute_name in ("embedding_model", "llm"):
        component = getattr(memory, attribute_name, None)
        client = getattr(component, "client", None)
        if not isinstance(client, OpenAI):
            continue
        try:
            setattr(
                component,
                "client",
                OpenAI(
                    api_key=client.api_key,
                    base_url=str(client.base_url),
                    timeout=request_timeout,
                    max_retries=2,
                ),
            )
        except Exception as exc:
            logger.warning(
                "could not apply mem0 %s http timeout: %s",
                attribute_name,
                type(exc).__name__,
            )


def _normalize_support(value: List[str]) -> List[str]:
    support = [str(item or "").strip() for item in value]
    if not support or any(not item for item in support):
        raise ValueError("support must contain non-empty evidence")
    return support


class TeacherStyleMemorySignal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    memory_type: Literal["teacher_style"]
    memory_text: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    support: List[SupportText] = Field(min_length=1, max_length=12)

    @field_validator("memory_text")
    @classmethod
    def normalize_memory_text(cls, value: str) -> str:
        text = str(value or "").strip()
        if not text:
            raise ValueError("memory_text must not be empty")
        return text

    @field_validator("support")
    @classmethod
    def normalize_support(cls, value: List[str]) -> List[str]:
        return _normalize_support(value)


class StudentFactMemorySignal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    memory_type: Literal["student_fact"]
    student_name: str = ""
    student_id_hint: Optional[int] = None
    memory_text: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    support: List[SupportText] = Field(min_length=1, max_length=12)

    @field_validator("student_name", "memory_text")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return str(value or "").strip()

    @field_validator("student_id_hint")
    @classmethod
    def validate_student_id_hint(cls, value: Optional[int]) -> Optional[int]:
        if value is not None and (isinstance(value, bool) or value <= 0):
            raise ValueError("student_id_hint must be a positive integer")
        return value

    @field_validator("support")
    @classmethod
    def normalize_support(cls, value: List[str]) -> List[str]:
        return _normalize_support(value)

    @model_validator(mode="after")
    def validate_student_hint(self) -> "StudentFactMemorySignal":
        if not self.student_name and self.student_id_hint is None:
            raise ValueError("student_fact must include a student hint")
        if not self.memory_text:
            raise ValueError("memory_text must not be empty")
        return self


class EvaluationOnlyMemorySignal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    memory_type: Literal["evaluation_only"]
    memory_text: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    support: List[SupportText] = Field(min_length=1, max_length=12)

    @field_validator("memory_text", "reason")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        text = str(value or "").strip()
        if not text:
            raise ValueError("value must not be empty")
        return text

    @field_validator("support")
    @classmethod
    def normalize_support(cls, value: List[str]) -> List[str]:
        return _normalize_support(value)


ClassCommentaryMemorySignal = Annotated[
    Union[TeacherStyleMemorySignal, StudentFactMemorySignal, EvaluationOnlyMemorySignal],
    Field(discriminator="memory_type"),
]


class ClassCommentaryMemoryExtraction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: List[ClassCommentaryMemorySignal] = Field(default_factory=list)


def parse_class_commentary_memory_extraction(payload: object) -> ClassCommentaryMemoryExtraction:
    if isinstance(payload, str):
        payload = json.loads(payload)
    if isinstance(payload, list):
        payload = {"items": payload}
    return ClassCommentaryMemoryExtraction.model_validate(payload)


class ClassCommentaryMemoryError(RuntimeError):
    pass


class ClassCommentaryMemoryDisabledError(ClassCommentaryMemoryError):
    pass


class ClassCommentaryMemoryConfigError(ClassCommentaryMemoryError):
    pass


class ClassCommentaryMemoryResponseError(ClassCommentaryMemoryError):
    pass


@dataclass(frozen=True)
class ClassCommentaryMemorySettings:
    enabled: bool
    vector_provider: str
    qdrant_url: str
    qdrant_api_key: str
    collection_name: str
    embedder_provider: str
    embedder_model: str
    embedding_dims: int
    style_limit: int
    student_limit: int
    context_char_limit: int


_CANONICAL_SUBJECT_KEY = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
_REQUIRED_PROJECTION_METADATA = {
    "organization_id",
    "scope_skill_registry_id",
    "student_id",
    "subject_key",
    "memory_type",
    "generation_id",
    "created_from_revision_id",
    "memory_record_id",
    "record_version",
    "evidence_count",
    "operation_key",
    "status",
    "confidence",
    "occurred_at",
}
_KNOWN_METADATA_KEYS = _REQUIRED_PROJECTION_METADATA | {"source_teacher_user_id", "source_skill_id"}


def _positive_int(value: object, *, name: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a positive integer")
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a positive integer") from exc
    if result <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return result


def _positive_setting(value: object, *, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _nonnegative_int(value: object, *, name: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a non-negative integer")
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a non-negative integer") from exc
    if result < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return result


def _setting(config: Mapping[str, object], key: str, default: object = "") -> object:
    return config.get(key, default)


def _class_commentary_llm_config(
    runtime_config: Mapping[str, object],
) -> Tuple[str, str, str]:
    config = dict(runtime_config)
    provider = config_runtime.resolve_class_commentary_provider(config)
    model = config_runtime.resolve_class_commentary_model(config, provider=provider)
    if provider == "deepseek":
        api_key = str(config.get("deepseek_api_key") or "").strip()
        base_url = "https://api.deepseek.com/v1"
    else:
        api_key = str(
            config.get("class_commentary_openai_api_key")
            or config.get("openai_api_key")
            or ""
        ).strip()
        base_url = str(
            config.get("class_commentary_openai_base_url")
            or config.get("openai_base_url")
            or "https://api.openai.com/v1"
        ).strip()
    return model, api_key, base_url


def load_class_commentary_memory_settings(
    runtime_config: Optional[Mapping[str, object]] = None,
) -> ClassCommentaryMemorySettings:
    config = dict(runtime_config if runtime_config is not None else config_runtime.get_runtime_config())
    defaults = config_runtime.DEFAULTS

    def numeric(key: str) -> int:
        default = int(defaults[key])
        return _positive_setting(config.get(key, default), default=default)

    return ClassCommentaryMemorySettings(
        enabled=config_runtime.normalize_bool_flag(
            config.get("class_commentary_memory_enabled", defaults["class_commentary_memory_enabled"])
        ),
        vector_provider=str(
            config.get("mem0_vector_provider", defaults["mem0_vector_provider"])
            or defaults["mem0_vector_provider"]
        ).strip(),
        qdrant_url=str(config.get("mem0_qdrant_url", defaults["mem0_qdrant_url"])).strip(),
        qdrant_api_key=str(config.get("mem0_qdrant_api_key", defaults["mem0_qdrant_api_key"])).strip(),
        collection_name=str(
            config.get("mem0_collection_name", defaults["mem0_collection_name"])
            or defaults["mem0_collection_name"]
        ).strip(),
        embedder_provider=str(
            config.get("mem0_embedder_provider", defaults["mem0_embedder_provider"])
        ).strip(),
        embedder_model=str(
            config.get("mem0_embedder_model", defaults["mem0_embedder_model"])
        ).strip(),
        embedding_dims=numeric("mem0_embedding_dims"),
        style_limit=numeric("mem0_style_limit"),
        student_limit=numeric("mem0_student_limit"),
        context_char_limit=numeric("mem0_context_char_limit"),
    )


class ClassCommentaryMemoryService:
    """Mem0 projection adapter. Returned memories remain untrusted SQLite candidates."""

    def __init__(
        self,
        *,
        client: Optional[object] = None,
        runtime_config: Optional[Mapping[str, object]] = None,
        enabled: Optional[bool] = None,
    ) -> None:
        self._runtime_config = dict(
            runtime_config if runtime_config is not None else config_runtime.get_runtime_config()
        )
        settings = load_class_commentary_memory_settings(self._runtime_config)
        if enabled is not None:
            settings = ClassCommentaryMemorySettings(
                enabled=bool(enabled),
                vector_provider=settings.vector_provider,
                qdrant_url=settings.qdrant_url,
                qdrant_api_key=settings.qdrant_api_key,
                collection_name=settings.collection_name,
                embedder_provider=settings.embedder_provider,
                embedder_model=settings.embedder_model,
                embedding_dims=settings.embedding_dims,
                style_limit=settings.style_limit,
                student_limit=settings.student_limit,
                context_char_limit=settings.context_char_limit,
            )
        self.settings = settings
        self._client = client

    @property
    def enabled(self) -> bool:
        return self.settings.enabled

    @staticmethod
    def style_user_id(organization_id: object, scope_skill_registry_id: object) -> str:
        organization = _positive_int(organization_id, name="organization_id")
        skill_registry = _positive_int(scope_skill_registry_id, name="scope_skill_registry_id")
        return f"cc:org:{organization}:skill:{skill_registry}:teacher-style"

    @staticmethod
    def student_user_id(organization_id: object, student_id: object, subject_key: object) -> str:
        organization = _positive_int(organization_id, name="organization_id")
        student = _positive_int(student_id, name="student_id")
        subject = str(subject_key or "").strip()
        if not _CANONICAL_SUBJECT_KEY.fullmatch(subject):
            raise ValueError("subject_key must be canonical")
        return f"cc:org:{organization}:student:{student}:subject:{subject}:student-fact"

    def _build_client(self) -> object:
        missing = []
        if not self.settings.qdrant_url:
            missing.append("XR_MEM0_QDRANT_URL")
        if not self.settings.embedder_provider:
            missing.append("XR_MEM0_EMBEDDER_PROVIDER")
        if not self.settings.embedder_model:
            missing.append("XR_MEM0_EMBEDDER_MODEL")
        if self.settings.embedding_dims <= 0:
            missing.append("XR_MEM0_EMBEDDING_DIMS")
        commentary_provider = config_runtime.resolve_class_commentary_provider(
            self._runtime_config
        )
        llm_model, llm_api_key, llm_base_url = _class_commentary_llm_config(
            self._runtime_config
        )
        if not llm_model:
            missing.append("XR_CLASS_COMMENTARY_MODEL")
        if not llm_api_key:
            missing.append(
                "DEEPSEEK_API_KEY"
                if commentary_provider == "deepseek"
                else "XR_CLASS_COMMENTARY_OPENAI_API_KEY or OPENAI_API_KEY"
            )
        if not llm_base_url:
            missing.append("XR_CLASS_COMMENTARY_OPENAI_BASE_URL")

        embedder_api_key = ""
        embedder_base_url = ""
        if self.settings.embedder_provider == "openai":
            embedder_api_key = str(
                self._runtime_config.get("mem0_embedder_api_key")
                or self._runtime_config.get("openai_api_key")
                or ""
            ).strip()
            embedder_base_url = str(
                self._runtime_config.get("mem0_embedder_base_url")
                or self._runtime_config.get("openai_base_url")
                or ""
            ).strip()
            if not embedder_api_key and commentary_provider == "openai":
                embedder_api_key = str(
                    self._runtime_config.get("class_commentary_openai_api_key") or ""
                ).strip()
                if not embedder_base_url:
                    embedder_base_url = str(
                        self._runtime_config.get("class_commentary_openai_base_url") or ""
                    ).strip()
            if not embedder_api_key:
                missing.append(
                    "XR_MEM0_EMBEDDER_API_KEY or OPENAI_API_KEY for the Mem0 embedder"
                )
        if missing:
            raise ClassCommentaryMemoryConfigError(
                "Missing class commentary memory settings: " + ", ".join(missing)
            )

        vector_config: Dict[str, object] = {
            "url": self.settings.qdrant_url,
            "collection_name": self.settings.collection_name,
            "embedding_model_dims": self.settings.embedding_dims,
        }
        if self.settings.qdrant_api_key:
            vector_config["api_key"] = self.settings.qdrant_api_key
        request_timeout = _positive_setting(
            _setting(self._runtime_config, "mem0_request_timeout_seconds", 30),
            default=30,
        )
        _attach_timed_qdrant_client(
            vector_config,
            self.settings.qdrant_url,
            self.settings.qdrant_api_key,
            request_timeout,
        )

        embedder_config: Dict[str, object] = {
            "model": self.settings.embedder_model,
            "embedding_dims": self.settings.embedding_dims,
        }
        if self.settings.embedder_provider == "openai":
            embedder_config["api_key"] = embedder_api_key
            if embedder_base_url:
                embedder_config["openai_base_url"] = embedder_base_url

        try:
            from mem0 import Memory
        except ImportError as exc:
            raise ClassCommentaryMemoryConfigError(
                "mem0ai is required when class commentary memory is enabled"
            ) from exc

        memory = Memory.from_config(
            {
                "vector_store": {
                    "provider": self.settings.vector_provider,
                    "config": vector_config,
                },
                "embedder": {
                    "provider": self.settings.embedder_provider,
                    "config": embedder_config,
                },
                "llm": {
                    "provider": "openai",
                    "config": {
                        "model": llm_model,
                        "api_key": llm_api_key,
                        "openai_base_url": llm_base_url,
                    },
                },
            }
        )
        _prepare_local_bm25_encoder(memory)
        _apply_openai_http_timeouts(memory, request_timeout)
        return memory

    def _require_client(self) -> object:
        if not self.enabled:
            raise ClassCommentaryMemoryDisabledError("Class commentary memory is disabled")
        if self._client is None:
            self._client = self._build_client()
        return self._client

    @staticmethod
    def _normalize_item(raw_item: object) -> Optional[Dict[str, object]]:
        if hasattr(raw_item, "model_dump"):
            raw_item = raw_item.model_dump()
        if not isinstance(raw_item, Mapping):
            return None

        raw = dict(raw_item)
        metadata_value = raw.get("metadata")
        metadata = dict(metadata_value) if isinstance(metadata_value, Mapping) else {}
        for key in _KNOWN_METADATA_KEYS:
            if key in raw and key not in metadata:
                metadata[key] = raw[key]

        memory_id = raw.get("id") or raw.get("memory_id")
        memory_text = raw.get("memory")
        if memory_text is None:
            memory_text = raw.get("text")
        if memory_text is None and isinstance(raw.get("data"), str):
            memory_text = raw.get("data")

        result: Dict[str, object] = {
            "id": str(memory_id) if memory_id is not None else "",
            "memory": str(memory_text or ""),
            "metadata": metadata,
        }
        if raw.get("user_id") is not None:
            result["user_id"] = str(raw["user_id"])
        if raw.get("score") is not None:
            result["score"] = raw["score"]
        if raw.get("event") is not None:
            result["event"] = raw["event"]
        return result

    @classmethod
    def _normalize_items(cls, response: object) -> List[Dict[str, object]]:
        if response is None:
            return []
        if hasattr(response, "model_dump"):
            response = response.model_dump()

        raw_items: object = response
        if isinstance(response, Mapping):
            for key in ("results", "memories", "data"):
                value = response.get(key)
                if isinstance(value, (list, tuple)):
                    raw_items = value
                    break
            else:
                raw_items = [response]
        if not isinstance(raw_items, (list, tuple)):
            return []

        items = []
        for raw_item in raw_items:
            item = cls._normalize_item(raw_item)
            if item is not None:
                items.append(item)
        return items

    @staticmethod
    def _style_scope(
        organization_id: object, scope_skill_registry_id: object
    ) -> Tuple[str, Dict[str, object]]:
        organization = _positive_int(organization_id, name="organization_id")
        skill_registry = _positive_int(scope_skill_registry_id, name="scope_skill_registry_id")
        return (
            ClassCommentaryMemoryService.style_user_id(organization, skill_registry),
            {
                "organization_id": organization,
                "scope_skill_registry_id": skill_registry,
                "memory_type": "teacher_style",
            },
        )

    @staticmethod
    def _student_scope(
        organization_id: object, student_id: object, subject_key: object
    ) -> Tuple[str, Dict[str, object]]:
        organization = _positive_int(organization_id, name="organization_id")
        student = _positive_int(student_id, name="student_id")
        subject = str(subject_key or "").strip()
        user_id = ClassCommentaryMemoryService.student_user_id(organization, student, subject)
        return (
            user_id,
            {
                "organization_id": organization,
                "student_id": student,
                "subject_key": subject,
                "memory_type": "student_fact",
            },
        )

    @classmethod
    def _scope_from_metadata(cls, metadata: Mapping[str, object]) -> Tuple[str, Dict[str, object]]:
        memory_type = str(metadata.get("memory_type") or "")
        if memory_type == "teacher_style":
            if metadata.get("student_id") is not None or metadata.get("subject_key") is not None:
                raise ValueError("teacher_style metadata cannot use student scope")
            return cls._style_scope(
                metadata.get("organization_id"), metadata.get("scope_skill_registry_id")
            )
        if memory_type == "student_fact":
            if metadata.get("scope_skill_registry_id") is not None:
                raise ValueError("student_fact metadata cannot use skill scope")
            return cls._student_scope(
                metadata.get("organization_id"), metadata.get("student_id"), metadata.get("subject_key")
            )
        raise ValueError("memory_type must be teacher_style or student_fact")

    @classmethod
    def _validate_projection_metadata(cls, metadata: Mapping[str, object]) -> Dict[str, object]:
        normalized = dict(metadata)
        missing = sorted(_REQUIRED_PROJECTION_METADATA - set(normalized))
        if missing:
            raise ValueError("Missing projection metadata: " + ", ".join(missing))

        for key in (
            "organization_id",
            "generation_id",
            "created_from_revision_id",
            "memory_record_id",
            "record_version",
        ):
            normalized[key] = _positive_int(normalized.get(key), name=key)
        normalized["evidence_count"] = _nonnegative_int(
            normalized.get("evidence_count"), name="evidence_count"
        )
        if normalized.get("memory_type") == "teacher_style":
            normalized["scope_skill_registry_id"] = _positive_int(
                normalized.get("scope_skill_registry_id"), name="scope_skill_registry_id"
            )
        elif normalized.get("memory_type") == "student_fact":
            normalized["student_id"] = _positive_int(normalized.get("student_id"), name="student_id")
            normalized["subject_key"] = str(normalized.get("subject_key") or "").strip()
        cls._scope_from_metadata(normalized)

        status = str(normalized.get("status") or "")
        if status not in {"active", "superseded", "revoked", "deleted"}:
            raise ValueError("status is invalid")
        normalized["status"] = status

        operation_key = str(normalized.get("operation_key") or "").strip()
        occurred_at = str(normalized.get("occurred_at") or "").strip()
        if not operation_key or not occurred_at:
            raise ValueError("operation_key and occurred_at are required")
        normalized["operation_key"] = operation_key
        normalized["occurred_at"] = occurred_at

        try:
            confidence = float(normalized.get("confidence"))
        except (TypeError, ValueError) as exc:
            raise ValueError("confidence must be between 0 and 1") from exc
        if confidence < 0 or confidence > 1:
            raise ValueError("confidence must be between 0 and 1")
        normalized["confidence"] = confidence
        return normalized

    @staticmethod
    def _matches_scope(
        item: Mapping[str, object], user_id: str, expected_metadata: Mapping[str, object]
    ) -> bool:
        item_user_id = str(item.get("user_id") or "")
        if item_user_id and item_user_id != user_id:
            return False
        metadata = item.get("metadata")
        if not isinstance(metadata, Mapping):
            return False
        return all(metadata.get(key) == value for key, value in expected_metadata.items())

    def add_projection(self, *, memory_text: str, metadata: Mapping[str, object]) -> Dict[str, object]:
        text = str(memory_text or "").strip()
        if not text:
            raise ValueError("memory_text must not be empty")
        normalized_metadata = self._validate_projection_metadata(metadata)
        user_id, _ = self._scope_from_metadata(normalized_metadata)
        response = self._require_client().add(
            text,
            user_id=user_id,
            metadata=normalized_metadata,
            infer=False,
        )
        items = self._normalize_items(response)
        if len(items) != 1 or not items[0].get("id"):
            raise ClassCommentaryMemoryResponseError("Mem0 add did not return one memory ID")
        return items[0]

    def update(
        self,
        memory_id: object,
        *,
        metadata: Mapping[str, object],
        memory_text: Optional[str] = None,
    ) -> object:
        memory_key = str(memory_id or "").strip()
        if not memory_key:
            raise ValueError("memory_id must not be empty")
        normalized_metadata = self._validate_projection_metadata(metadata)
        text = None if memory_text is None else str(memory_text or "").strip()
        if memory_text is not None and not text:
            raise ValueError("memory_text must not be empty")
        update_method = self._require_client().update
        update_parameters = inspect.signature(update_method).parameters
        text_parameter = "text" if "text" in update_parameters else "data"
        return update_method(
            memory_key,
            **{
                text_parameter: text,
                "metadata": normalized_metadata,
            },
        )

    def delete(self, memory_id: object) -> object:
        memory_key = str(memory_id or "").strip()
        if not memory_key:
            raise ValueError("memory_id must not be empty")
        return self._require_client().delete(memory_key)

    def get(self, memory_id: object) -> Optional[Dict[str, object]]:
        memory_key = str(memory_id or "").strip()
        if not memory_key:
            raise ValueError("memory_id must not be empty")
        items = self._normalize_items(self._require_client().get(memory_key))
        return items[0] if items else None

    def find_by_operation_key(
        self,
        operation_key: object,
        *,
        organization_id: object,
        memory_type: MemoryType,
        scope_skill_registry_id: Optional[object] = None,
        student_id: Optional[object] = None,
        subject_key: Optional[object] = None,
    ) -> Optional[Dict[str, object]]:
        operation = str(operation_key or "").strip()
        if not operation:
            raise ValueError("operation_key must not be empty")
        if memory_type == "teacher_style":
            user_id, scope = self._style_scope(organization_id, scope_skill_registry_id)
        elif memory_type == "student_fact":
            user_id, scope = self._student_scope(organization_id, student_id, subject_key)
        else:
            raise ValueError("memory_type must be teacher_style or student_fact")
        expected = dict(scope)
        expected["operation_key"] = operation
        filters = {"user_id": user_id, **expected}
        response = self._require_client().get_all(filters=filters, top_k=2)
        items = self._normalize_items(response)
        matches = [item for item in items if self._matches_scope(item, user_id, expected)]
        if len(matches) > 1:
            raise ClassCommentaryMemoryResponseError(
                "Mem0 returned duplicate projections for one operation key"
            )
        return matches[0] if matches else None

    def search_style(
        self,
        query: object,
        *,
        organization_id: object,
        scope_skill_registry_id: object,
        limit: Optional[int] = None,
    ) -> List[Dict[str, object]]:
        query_text = str(query or "").strip()
        if not query_text:
            return []
        user_id, expected = self._style_scope(organization_id, scope_skill_registry_id)
        result_limit = _positive_setting(limit, default=self.settings.style_limit)
        response = self._require_client().search(
            query_text,
            filters={"user_id": user_id, **expected},
            top_k=result_limit,
        )
        return [
            item
            for item in self._normalize_items(response)
            if self._matches_scope(item, user_id, expected)
        ][:result_limit]

    def search_student(
        self,
        query: object,
        *,
        organization_id: object,
        student_id: object,
        subject_key: object,
        limit: Optional[int] = None,
    ) -> List[Dict[str, object]]:
        query_text = str(query or "").strip()
        if not query_text:
            return []
        user_id, expected = self._student_scope(organization_id, student_id, subject_key)
        result_limit = _positive_setting(limit, default=self.settings.student_limit)
        response = self._require_client().search(
            query_text,
            filters={"user_id": user_id, **expected},
            top_k=result_limit,
        )
        return [
            item
            for item in self._normalize_items(response)
            if self._matches_scope(item, user_id, expected)
        ][:result_limit]

    def healthcheck(self) -> Dict[str, object]:
        if not self.enabled:
            return {"enabled": False, "healthy": False, "status": "disabled"}
        client = None
        memory_id = ""
        try:
            client = self._require_client()
            probe_id = uuid.uuid4().hex
            response = client.add(
                f"class-commentary-memory-healthcheck:{probe_id}",
                user_id=f"cc:class-commentary-memory-healthcheck:{probe_id}",
                metadata={"healthcheck_id": probe_id},
                infer=False,
            )
            added_items = self._normalize_items(response)
            if len(added_items) != 1 or not added_items[0].get("id"):
                raise ClassCommentaryMemoryResponseError(
                    "Mem0 healthcheck add did not return one memory ID"
                )
            memory_id = str(added_items[0]["id"])
            stored_items = self._normalize_items(client.get(memory_id))
            if not any(item.get("id") == memory_id for item in stored_items):
                raise ClassCommentaryMemoryResponseError(
                    "Mem0 healthcheck could not read the probe memory"
                )
            searched_items = self._normalize_items(
                client.search(
                    f"class-commentary-memory-healthcheck:{probe_id}",
                    filters={
                        "user_id": f"cc:class-commentary-memory-healthcheck:{probe_id}"
                    },
                    top_k=1,
                )
            )
            if not any(item.get("id") == memory_id for item in searched_items):
                raise ClassCommentaryMemoryResponseError(
                    "Mem0 healthcheck could not search the probe memory"
                )
            client.delete(memory_id)
            memory_id = ""
        except Exception as exc:
            logger.warning(
                "class commentary memory healthcheck unavailable: %s",
                type(exc).__name__,
                exc_info=True,
            )
            return {
                "enabled": True,
                "healthy": False,
                "status": "unavailable",
                "error_type": type(exc).__name__,
            }
        finally:
            if client is not None and memory_id:
                try:
                    client.delete(memory_id)
                except Exception:
                    logger.warning(
                        "class commentary memory healthcheck probe cleanup failed",
                        exc_info=True,
                    )
        return {"enabled": True, "healthy": True, "status": "ready"}

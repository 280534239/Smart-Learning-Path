"""练习题加载、自动批改与错题本业务逻辑。"""

import asyncio
import json
import logging
import random
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.attempt_record import AttemptRecord
from app.models.error_book import ErrorBook
from app.models.user import User
from app.schemas.practice import (
    ErrorBookData,
    ErrorBookItem,
    PracticeQuestion,
    PracticeQuestionData,
    QuestionBankDocument,
    QuestionRecord,
    ReviewErrorData,
    SubmitAnswerData,
)
from app.services.knowledge_service import (
    KnowledgePointNotFoundError,
    knowledge_service,
)
from app.services.knowledge_tracer import knowledge_tracer
from app.services.content_generation_service import (
    ContentGenerationError,
    ContentGenerationUnavailableError,
    content_generation_service,
)

GENERATED_QUESTION_DIR = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "generated_questions"
)

logger = logging.getLogger(__name__)


class PracticeNotFoundError(Exception):
    """练习模块请求的资源不存在。"""


@dataclass(frozen=True, slots=True)
class LoadedQuestionBank:
    """预加载后的内存题库索引。"""

    questions_by_id: dict[str, QuestionRecord]
    questions_by_point: dict[str, tuple[QuestionRecord, ...]]


class PracticeService:
    """管理题目的加载、筛选、提交和错题本。"""

    def __init__(self) -> None:
        self._bank: LoadedQuestionBank | None = None
        self._question_subject_by_id: dict[str, str] = {}
        self._generated_question_ids: set[str] = set()
        self._load_lock = asyncio.Lock()
        self._generation_locks: dict[str, asyncio.Lock] = {}
        self._registration_lock = asyncio.Lock()

    async def load_all(self, *, force: bool = False) -> None:
        """从 JSON 文件加载题库并建立知识点索引。"""
        async with self._load_lock:
            if self._bank is not None and not force:
                return

            documents = await self._load_question_documents()
            questions_by_id: dict[str, QuestionRecord] = {}
            grouped: dict[str, list[QuestionRecord]] = {}
            question_subject_by_id: dict[str, str] = {}
            generated_question_ids: set[str] = set()
            for subject, document, is_generated in documents:
                await self._validate_document(document)
                for question in document.questions:
                    if question.id in questions_by_id:
                        logger.warning(
                            "跳过重复题目 ID: %s (%s)",
                            question.id,
                            subject,
                        )
                        continue
                    questions_by_id[question.id] = question
                    question_subject_by_id[question.id] = subject
                    if is_generated:
                        generated_question_ids.add(question.id)
                    grouped.setdefault(
                        question.knowledge_point_id,
                        [],
                    ).append(question)

            self._bank = LoadedQuestionBank(
                questions_by_id=questions_by_id,
                questions_by_point={
                    point_id: tuple(questions)
                    for point_id, questions in grouped.items()
                },
            )
            self._question_subject_by_id = question_subject_by_id
            self._generated_question_ids = generated_question_ids

    @staticmethod
    def _read_question_file(path: Path) -> dict[str, Any]:
        """读取原始题库 JSON。"""
        return json.loads(path.read_text(encoding="utf-8"))

    async def _load_question_documents(
        self,
    ) -> list[tuple[str, QuestionBankDocument, bool]]:
        """读取模型生成并持久化的题库。"""
        paths: list[tuple[Path, bool]] = []
        if GENERATED_QUESTION_DIR.exists():
            paths = [
                (path, True)
                for path in sorted(GENERATED_QUESTION_DIR.glob("*.json"))
            ]

        documents: list[tuple[str, QuestionBankDocument, bool]] = []
        for path, is_generated in paths:
            if not path.is_file():
                continue
            try:
                raw_data = await asyncio.to_thread(
                    self._read_question_file,
                    path,
                )
                document = QuestionBankDocument.model_validate(raw_data)
                documents.append(
                    (document.subject, document, is_generated)
                )
            except Exception:
                logger.exception("跳过无法加载的生成题库: %s", path)
        return documents

    @staticmethod
    async def _validate_document(document: QuestionBankDocument) -> None:
        """校验题目数量、ID 唯一性和知识点引用。"""
        if document.question_count != len(document.questions):
            raise ValueError("题库 question_count 与实际题目数不一致")
        if len({question.id for question in document.questions}) != len(
            document.questions
        ):
            raise ValueError("题库存在重复题目 ID")

        for question in document.questions:
            try:
                await knowledge_service.get_point(
                    question.knowledge_point_id
                )
            except KnowledgePointNotFoundError as exc:
                raise ValueError(
                    f"题目 {question.id} 引用了不存在的知识点"
                ) from exc

    async def _ensure_loaded(self) -> None:
        """确保题库已加载。"""
        if self._bank is None:
            await self.load_all()

    async def get_questions(
        self,
        knowledge_point_id: str,
        *,
        difficulty: int | None = None,
        count: int = 5,
        learning_goal: str | None = None,
    ) -> PracticeQuestionData:
        """按知识点和难度筛选题目，随机返回指定数量。"""
        await self._ensure_loaded()
        try:
            await knowledge_service.get_point(knowledge_point_id)
        except KnowledgePointNotFoundError as exc:
            raise PracticeNotFoundError(
                f"知识点不存在: {knowledge_point_id}"
            ) from exc
        subject = await knowledge_service.get_point_subject(
            knowledge_point_id
        )

        assert self._bank is not None
        available = list(
            self._bank.questions_by_point.get(knowledge_point_id, ())
        )
        if difficulty is not None:
            available = [
                question
                for question in available
                if question.difficulty == difficulty
            ]

        selected = (
            random.sample(available, min(count, len(available)))
            if available
            else []
        )
        if not selected:
            generation_lock = self._generation_locks.setdefault(
                knowledge_point_id,
                asyncio.Lock(),
            )
            async with generation_lock:
                available = list(
                    self._bank.questions_by_point.get(
                        knowledge_point_id,
                        (),
                    )
                )
                if difficulty is not None:
                    available = [
                        question
                        for question in available
                        if question.difficulty == difficulty
                    ]
                selected = (
                    random.sample(
                        available,
                        min(count, len(available)),
                    )
                    if available
                    else []
                )
                if not selected:
                    point = await knowledge_service.get_point(
                        knowledge_point_id
                    )
                    try:
                        generated = (
                            await content_generation_service.generate_questions(
                                subject=subject,
                                point=point,
                                difficulty=difficulty or point.difficulty,
                                count=count,
                                learning_goal=learning_goal,
                            )
                        )
                        async with self._registration_lock:
                            selected = await self._register_generated_questions(
                                subject=subject,
                                knowledge_point_id=knowledge_point_id,
                                generated=generated,
                            )
                    except ContentGenerationUnavailableError:
                        logger.info(
                            "未配置模型，无法为知识点生成题目: %s",
                            knowledge_point_id,
                        )
                    except ContentGenerationError:
                        logger.exception(
                            "模型题目生成失败: %s",
                            knowledge_point_id,
                        )

        questions = [
            PracticeQuestion(
                id=question.id,
                knowledge_point_id=question.knowledge_point_id,
                type=question.type,
                difficulty=question.difficulty,
                question=question.question,
                options=question.options,
            )
            for question in selected
        ]
        return PracticeQuestionData(
            subject=subject,
            knowledge_point_id=knowledge_point_id,
            count=len(questions),
            questions=questions,
        )

    async def get_all_questions(self) -> list[QuestionRecord]:
        """返回完整题库，供向量索引等内部服务使用。"""
        await self._ensure_loaded()
        assert self._bank is not None
        return list(self._bank.questions_by_id.values())

    async def get_question(self, question_id: str) -> QuestionRecord:
        """按题目 ID 返回完整题目，供权限校验与内部流程使用。"""
        await self._ensure_loaded()
        assert self._bank is not None
        question = self._bank.questions_by_id.get(question_id)
        if question is None:
            raise PracticeNotFoundError(f"题目不存在: {question_id}")
        return question

    async def _register_generated_questions(
        self,
        *,
        subject: str,
        knowledge_point_id: str,
        generated: list[dict[str, Any]],
    ) -> list[QuestionRecord]:
        """校验并登记模型题目，同时持久化到生成题库。"""
        await self._ensure_loaded()
        assert self._bank is not None
        registered: list[QuestionRecord] = []

        for payload in generated:
            question_id = (
                f"ai_{subject[-12:]}_{uuid4().hex[:10]}"
            )
            record = QuestionRecord.model_validate(
                {
                    **payload,
                    "id": question_id,
                    "knowledge_point_id": knowledge_point_id,
                }
            )
            registered.append(record)

        if not registered:
            return []

        for record in registered:
            self._bank.questions_by_id[record.id] = record
            existing = list(
                self._bank.questions_by_point.get(
                    record.knowledge_point_id,
                    (),
                )
            )
            existing.append(record)
            self._bank.questions_by_point[record.knowledge_point_id] = tuple(
                existing
            )
            self._question_subject_by_id[record.id] = subject
            self._generated_question_ids.add(record.id)

        await self._persist_generated_questions(subject)
        return registered

    async def _persist_generated_questions(self, subject: str) -> None:
        """将某个学习内容的模型题目保存为可重复加载的题库。"""
        assert self._bank is not None
        questions = [
            question
            for question_id, question in self._bank.questions_by_id.items()
            if self._question_subject_by_id.get(question_id) == subject
            and question_id in self._generated_question_ids
        ]
        questions.sort(key=lambda question: question.id)
        document = QuestionBankDocument(
            subject=subject,
            version="generated-1.0.0",
            description="模型按知识点即时生成并持久化的练习题",
            question_count=len(questions),
            questions=questions,
        )

        GENERATED_QUESTION_DIR.mkdir(parents=True, exist_ok=True)
        filename = (
            f"{subject}.json"
            if subject.startswith("custom_")
            else f"{subject}_ai.json"
        )
        path = GENERATED_QUESTION_DIR / filename
        temporary_path = path.with_suffix(".json.tmp")
        payload = document.model_dump(mode="json")
        await asyncio.to_thread(
            temporary_path.write_text,
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary_path.replace(path)

    async def submit_answer(
        self,
        *,
        user_id: int,
        question_id: str,
        answer: str,
        time_spent: int,
        session: AsyncSession,
    ) -> SubmitAnswerData:
        """自动批改答案、写入答题记录并更新错题本。"""
        await self._ensure_loaded()
        assert self._bank is not None
        question = self._bank.questions_by_id.get(question_id)
        if question is None:
            raise PracticeNotFoundError(f"题目不存在: {question_id}")
        if await session.get(User, user_id) is None:
            raise PracticeNotFoundError(f"用户不存在: {user_id}")

        subject = await knowledge_service.get_point_subject(
            question.knowledge_point_id
        )
        is_correct = self._grade_answer(question, answer)
        session.add(
            AttemptRecord(
                user_id=user_id,
                subject=subject,
                question_id=question.id,
                knowledge_point_id=question.knowledge_point_id,
                user_answer=answer,
                is_correct=is_correct,
                time_spent=time_spent,
                error_type=(
                    None if is_correct else f"{question.type}_error"
                ),
            )
        )

        if not is_correct:
            await self._upsert_error_book(
                user_id=user_id,
                subject=subject,
                question=question,
                user_answer=answer,
                session=session,
            )

        await session.commit()
        mastery = await knowledge_tracer.calculate_mastery(
            user_id,
            question.knowledge_point_id,
            session,
        )
        return SubmitAnswerData(
            subject=subject,
            is_correct=is_correct,
            explanation=question.explanation,
            mastery_updated={
                question.knowledge_point_id: round(mastery.mastery, 4)
            },
        )

    async def submit_answers(
        self,
        *,
        user_id: int,
        answers: list[tuple[str, str, int]],
        session: AsyncSession,
        commit: bool = True,
    ) -> list[SubmitAnswerData]:
        """批量批改诊断答案，并在同一事务中写入答题记录。"""
        await self._ensure_loaded()
        assert self._bank is not None
        if await session.get(User, user_id) is None:
            raise PracticeNotFoundError(f"用户不存在: {user_id}")

        graded: list[tuple[QuestionRecord, str, bool]] = []
        for question_id, answer, time_spent in answers:
            question = self._bank.questions_by_id.get(question_id)
            if question is None:
                raise PracticeNotFoundError(f"题目不存在: {question_id}")
            subject = await knowledge_service.get_point_subject(
                question.knowledge_point_id
            )
            is_correct = self._grade_answer(question, answer)
            session.add(
                AttemptRecord(
                    user_id=user_id,
                    subject=subject,
                    question_id=question.id,
                    knowledge_point_id=question.knowledge_point_id,
                    user_answer=answer,
                    is_correct=is_correct,
                    time_spent=time_spent,
                    error_type=(
                        None if is_correct else f"{question.type}_error"
                    ),
                )
            )
            if not is_correct:
                await self._upsert_error_book(
                    user_id=user_id,
                    subject=subject,
                    question=question,
                    user_answer=answer,
                    session=session,
                )
            graded.append((question, subject, is_correct))

        if commit:
            await session.commit()
        else:
            await session.flush()
        mastery_by_point = {}
        for question, _, _ in graded:
            if question.knowledge_point_id in mastery_by_point:
                continue
            mastery = await knowledge_tracer.calculate_mastery(
                user_id,
                question.knowledge_point_id,
                session,
            )
            mastery_by_point[question.knowledge_point_id] = round(
                mastery.mastery,
                4,
            )

        return [
            SubmitAnswerData(
                subject=subject,
                is_correct=is_correct,
                explanation=question.explanation,
                mastery_updated={
                    question.knowledge_point_id: mastery_by_point[
                        question.knowledge_point_id
                    ]
                },
            )
            for question, subject, is_correct in graded
        ]

    async def _upsert_error_book(
        self,
        *,
        user_id: int,
        subject: str,
        question: QuestionRecord,
        user_answer: str,
        session: AsyncSession,
    ) -> None:
        """新增错题，或刷新已有错题的错误答案和掌握状态。"""
        entry = await session.scalar(
            select(ErrorBook).where(
                ErrorBook.user_id == user_id,
                ErrorBook.question_id == question.id,
            )
        )
        if entry is None:
            session.add(
                ErrorBook(
                    user_id=user_id,
                    subject=subject,
                    question_id=question.id,
                    knowledge_point_id=question.knowledge_point_id,
                    original_answer=user_answer,
                    correct_answer=question.answer,
                    review_count=0,
                    is_mastered=False,
                )
            )
            return

        entry.original_answer = user_answer
        entry.correct_answer = question.answer
        entry.knowledge_point_id = question.knowledge_point_id
        entry.subject = subject
        entry.is_mastered = False

    async def get_error_book(
        self,
        *,
        user_id: int,
        session: AsyncSession,
        subject: str,
        knowledge_point_id: str | None = None,
    ) -> ErrorBookData:
        """获取错题本，可按知识点筛选。"""
        await self._ensure_loaded()
        if await session.get(User, user_id) is None:
            raise PracticeNotFoundError(f"用户不存在: {user_id}")

        statement = select(ErrorBook).where(
            ErrorBook.user_id == user_id,
            ErrorBook.subject == subject,
        )
        if knowledge_point_id is not None:
            statement = statement.where(
                ErrorBook.knowledge_point_id == knowledge_point_id
            )
        statement = statement.order_by(ErrorBook.created_at.desc())
        entries = (await session.scalars(statement)).all()

        assert self._bank is not None
        items = [
            self._to_error_book_item(
                entry,
                self._bank.questions_by_id.get(entry.question_id),
            )
            for entry in entries
        ]
        return ErrorBookData(
            user_id=user_id,
            subject=subject,
            count=len(items),
            items=items,
        )

    async def review_error(
        self,
        *,
        user_id: int,
        error_book_id: int,
        session: AsyncSession,
    ) -> ReviewErrorData:
        """增加复习次数并将错题标记为已掌握。"""
        entry = await session.get(ErrorBook, error_book_id)
        if entry is None or entry.user_id != user_id:
            raise PracticeNotFoundError("错题记录不存在")

        entry.review_count += 1
        entry.is_mastered = True
        await session.commit()
        await session.refresh(entry)
        return ReviewErrorData(
            error_book_id=entry.id,
            review_count=entry.review_count,
            is_mastered=entry.is_mastered,
        )

    @staticmethod
    def _grade_answer(question: QuestionRecord, answer: str) -> bool:
        """按题型自动批改答案。"""
        normalized_answer = PracticeService._normalize_answer(answer)
        correct_answer = PracticeService._normalize_answer(question.answer)

        if question.type == "choice":
            return bool(
                re.match(
                    rf"^{re.escape(correct_answer)}(?:[.\s:：、]|$)",
                    normalized_answer,
                )
            )

        accepted_answers = {
            correct_answer,
            *(
                PracticeService._normalize_answer(value)
                for value in question.accepted_answers
            ),
        }
        return normalized_answer in accepted_answers

    @staticmethod
    def _normalize_answer(value: str) -> str:
        """统一大小写、全半角与连续空白，提升自动批改容错率。"""
        normalized = unicodedata.normalize("NFKC", value).strip().casefold()
        return re.sub(r"\s+", " ", normalized)

    @staticmethod
    def _to_error_book_item(
        entry: ErrorBook,
        question: QuestionRecord | None,
    ) -> ErrorBookItem:
        """将错题模型关联题库内容后转换为响应模型。"""
        return ErrorBookItem(
            id=entry.id,
            subject=entry.subject,
            question_id=entry.question_id,
            knowledge_point_id=entry.knowledge_point_id,
            question=(
                question.question if question else "题目数据已更新"
            ),
            question_type=question.type if question else "short_answer",
            difficulty=question.difficulty if question else 1,
            original_answer=entry.original_answer,
            correct_answer=entry.correct_answer,
            explanation=question.explanation if question else "",
            review_count=entry.review_count,
            is_mastered=entry.is_mastered,
            created_at=entry.created_at,
        )


practice_service = PracticeService()

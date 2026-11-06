"""学习目标优先级的归一化与语义评分。"""

import re
from collections.abc import Iterable

from app.schemas.knowledge import KnowledgePointNode

DEFAULT_GOAL = "建立系统、可实践的知识体系"
MAX_GOAL_PRIORITIES = 8
GOAL_SEPARATOR = "、"
GOAL_PRIORITY_WEIGHTS = (
    1.0,
    0.6,
    0.36,
    0.216,
    0.1296,
    0.07776,
    0.046656,
    0.0279936,
)

GOAL_INTENTS: dict[str, tuple[str, ...]] = {
    "快速入门": ("基础", "入门", "概念", "环境"),
    "夯实基础": ("基础", "核心", "概念", "原理"),
    "掌握核心概念": ("核心", "概念", "原理", "模型"),
    "理解底层原理": ("原理", "机制", "底层", "模型"),
    "提升解题能力": ("练习", "解题", "计算", "应用", "方法"),
    "应对考试": ("考试", "题型", "重点", "应用"),
    "完成实际项目": ("项目", "实践", "案例", "实现", "应用"),
    "拓展知识面": ("拓展", "进阶", "综合", "生态"),
}


def normalize_goal_priorities(
    priorities: Iterable[str] | None = None,
    goal: str | None = None,
) -> list[str]:
    """合并显式优先级与旧版目标字符串，去重并保留顺序。"""
    candidates = [
        str(item).strip()
        for item in (priorities or ())
        if str(item).strip()
    ]
    if goal:
        candidates.extend(
            item.strip()
            for item in re.split(r"[、,，;；>→]+", goal)
            if item.strip()
        )

    normalized: list[str] = []
    for item in candidates:
        cleaned = re.sub(r"^\d+[.、\s]*", "", item).strip()
        if not cleaned or cleaned in normalized:
            continue
        normalized.append(cleaned[:40])
        if len(normalized) >= MAX_GOAL_PRIORITIES:
            break
    return normalized


def format_goal_text(priorities: list[str]) -> str:
    """把优先级列表转换为现有学习目标存储格式。"""
    return GOAL_SEPARATOR.join(priorities) if priorities else DEFAULT_GOAL


def format_goal_priority_text(priorities: list[str]) -> str:
    """生成适合路径摘要展示的目标优先顺序。"""
    return " → ".join(priorities) if priorities else DEFAULT_GOAL


def goal_affinity(
    node: KnowledgePointNode,
    priorities: list[str],
) -> float:
    """按目标优先级计算知识点与学习目标的匹配度。"""
    if not priorities:
        return 0.0

    searchable = f"{node.name}{node.category}{''.join(node.tags)}"
    weights = GOAL_PRIORITY_WEIGHTS[:len(priorities)]
    total_weight = sum(weights)
    if total_weight <= 0:
        return 0.0

    weighted_score = 0.0
    for index, priority in enumerate(priorities):
        terms = GOAL_INTENTS.get(priority)
        if terms is None:
            terms = tuple(
                term
                for term in re.split(r"[\s、,，;；/]+", priority)
                if len(term) >= 2
            )
        if any(term in searchable for term in terms):
            weighted_score += weights[index]

    return min(1.0, weighted_score / total_weight)


__all__ = [
    "DEFAULT_GOAL",
    "GOAL_INTENTS",
    "MAX_GOAL_PRIORITIES",
    "format_goal_priority_text",
    "format_goal_text",
    "goal_affinity",
    "normalize_goal_priorities",
]

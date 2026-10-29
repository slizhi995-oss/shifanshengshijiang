"""
富演示数据 seed：为三端（admin/instructor/student）生成覆盖所有主要页面的真实数据。

触发条件：submissions 表为空时执行（幂等，已有 submissions 则跳过整块）。
附加：确保默认账号 teacher(id=teacher) / student(id=student) 已被分组到活跃批次。
"""
from __future__ import annotations

import json
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy import select, func

from app.core.database import async_session_factory
from app.core.security import hash_password  # noqa: F401  (kept for symmetry)


# ----------------------------------------------------------------------------
# 固定随机种子，确保每次生成的数据分布一致，便于回归
# ----------------------------------------------------------------------------
_RNG = random.Random(20260423)


# ----------------------------------------------------------------------------
# 文案池（做到"真实但避免长篇"）
# ----------------------------------------------------------------------------

_LP_SUMMARIES = [
    "整体教案结构清晰，教学目标与核心素养结合较好，教学过程设计逻辑顺畅，但导入环节偏长，板书设计细节可更精炼。",
    "教案目标表述精准，重难点突出，过程环节衔接自然，教学语言严谨。建议在互动提问上增加梯度化设计。",
    "整体呈现出新手教师的规范意识，部分环节深度不足；板书布局合理，但字迹规范度仍需加强练习。",
    "教学过程设计体现了探究式学习理念，学生活动丰富，评价环节反馈明确。建议精简导入时间至 3 分钟以内。",
    "教案围绕大概念展开，结构完整；教学方法多元，含有情境与任务驱动；部分术语不够准确，需再校对。",
]

_LP_HIGHLIGHTS_POOL = [
    "教学目标紧扣新课标，使用可观察可测量的行为动词",
    "导入情境贴近学生生活，能迅速调动课堂氛围",
    "重难点突出，并配套了分层练习，体现因材施教",
    "设计了学生合作探究环节，体现以学生为中心",
    "板书采用主副板书结构，条理清晰",
    "教学评价嵌入过程性观察，评价量规具体",
    "融入多媒体与实物教具，形式丰富",
]

_LP_SUGGESTIONS_POOL = [
    "导入环节可再紧凑，建议控制在 3 分钟以内",
    "学生活动的组织形式可更多样，避免长时间小组讨论",
    "板书书写需进一步规范，字体大小与间距更讲究",
    "提问设计可加入更多开放式、评价性问题",
    "课堂用语应避免口头禅，关键术语需规范",
    "对差异化学生的支持策略在教案中体现不足，可补充分层引导",
    "结尾升华部分可结合作业任务做情感铺垫",
]

_VIDEO_SUGGESTIONS_POOL = [
    "语速偏快，可在关键知识点处刻意放慢并停顿",
    "眼神交流集中在前排，建议均匀覆盖全场",
    "站姿略微僵硬，可适度走动并靠近学生",
    "手势动作较少，可在强调重点时配合手势",
    "板书过程背对学生时间较长，建议侧身书写",
    "语调相对平稳，可通过节奏变化吸引学生注意",
]

_TEACHING_SUBJECTS = ["语文", "数学", "英语", "物理", "历史", "生物", "地理", "道德与法治"]

_NOTICES = [
    {
        "title": "【重要】2025 春季批次第二次试讲作业提醒",
        "content": "<p>各位同学：第二次试讲作业（<b>新授课完整教学设计</b>）将于<span style='color:#d03'>5 月 30 日 23:59</span> 截止，请各位同学按时提交教案与视频。</p><ul><li>教案需包含教学目标、重难点、教学过程与板书设计</li><li>视频 15–20 分钟，需包含导入、新授、巩固练习、小结</li><li>如有特殊情况请提前与指导老师沟通</li></ul>",
        "is_pinned": True,
        "show_on_login": True,
        "display_type": "both",
    },
    {
        "title": "【讲座】新课标核心素养导向的教学设计 —— 线上讲座",
        "content": "<p>学院将于下周五晚 19:00 举办新课标讲座，由基础教育研究中心王教授主讲，主题为<b>『核心素养导向的教学设计转型』</b>。<br/>线上会议室：腾讯会议 <code>889-012-345</code>，请提前 10 分钟入场。</p>",
        "is_pinned": False,
        "show_on_login": False,
        "display_type": "dialog",
    },
    {
        "title": "【展播】2024 秋季批次优秀试讲作品展播",
        "content": "<p>经指导老师推荐，共 12 件优秀试讲作品入选本学期展播，已上架到『资源中心 → 优秀教学案例』栏目，欢迎各位同学学习参考。</p>",
        "is_pinned": False,
        "show_on_login": False,
        "display_type": "dialog",
    },
    {
        "title": "【系统】AI 评分服务使用指引",
        "content": "<p>平台 AI 评分功能现已稳定上线，提交作业后约 1–3 分钟即可在<b>『AI 报告』</b>中查看教案与视频的多维度评分与改进建议。若等待超过 10 分钟仍未生成，请联系管理员。</p>",
        "is_pinned": False,
        "show_on_login": False,
        "display_type": "marquee",
    },
    {
        "title": "【通知】系统维护公告（4 月 28 日凌晨 1:00-3:00）",
        "content": "<p>为提升服务稳定性，平台将于 4 月 28 日（周一）凌晨 1:00–3:00 进行例行维护，期间部分功能可能不可用。请合理安排作业提交时间，感谢配合。</p>",
        "is_pinned": False,
        "show_on_login": False,
        "display_type": "marquee",
    },
]

_MESSAGE_THREADS = [
    ("student", "teacher", "老师您好，第二次试讲的教案结构我按『起承转合』来写可以吗？"),
    ("teacher", "student", "可以的，注意起要引人入胜，转要有深度，承和合的比例要合理。"),
    ("student", "teacher", "好的！另外视频录制的时长有强制要求吗？"),
    ("teacher", "student", "建议严格控制在 15–20 分钟区间，方便评审对比。"),
    ("student", "teacher", "收到，谢谢老师！"),
]


_NOTIFICATIONS = [
    ("task", "新任务发布", "你的指导老师发布了新任务 『第二次试讲：新授课完整教学设计』，请按时提交。", "/student/tasks"),
    ("grade", "作业已评阅", "你的第一次试讲作业已评阅完成，总分 86 分，请在『我的成绩』中查看详情。", "/student/grades"),
    ("ai", "AI 分析完成", "你提交的教案 AI 分析已经生成，共 7 个维度评分，请前往『AI 报告』查看。", "/student/ai-report"),
    ("message", "您有新的留言", "指导老师给您留言了，请在『消息中心』中查看。", "/student/messages"),
    ("system", "平台公告", "2025 春季批次第二次试讲作业即将截止，请及时提交。", "/student/notices"),
]


_PRACTICE_TOPICS = [
    ("七年级语文 · 《春》朗读指导", "初一", "严谨型"),
    ("八年级数学 · 一次函数图象", "初二", "启发型"),
    ("高一英语 · 定语从句引入", "高一", "活泼型"),
    ("九年级物理 · 浮力概念建构", "初三", "耐心型"),
]


# ----------------------------------------------------------------------------
# 工具函数：生成 AI 分析 JSON（符合前端 AIReport 结构）
# ----------------------------------------------------------------------------

_LP_DIMENSIONS_KEYS = [
    "structure", "objectives", "key_points",
    "teaching_process", "teaching_methods",
    "board_design", "language",
]


def _gen_lesson_plan_analysis(base_score: float) -> dict:
    dims = {}
    for k in _LP_DIMENSIONS_KEYS:
        # 在 base_score 附近上下浮动 ±8
        s = max(55.0, min(98.0, base_score + _RNG.uniform(-8, 8)))
        dims[k] = {"score": round(s, 1)}
    overall = round(sum(d["score"] for d in dims.values()) / len(dims), 1)
    return {
        "overall_score": overall,
        "summary": _RNG.choice(_LP_SUMMARIES),
        "dimensions": dims,
        "highlights": _RNG.sample(_LP_HIGHLIGHTS_POOL, k=_RNG.randint(2, 4)),
        "suggestions": _RNG.sample(_LP_SUGGESTIONS_POOL, k=_RNG.randint(2, 4)),
    }


def _gen_video_analysis(base_score: float) -> dict:
    overall = round(max(55.0, min(95.0, base_score + _RNG.uniform(-6, 6))), 1)
    return {
        "overall_score": overall,
        "speech_rate": _RNG.randint(180, 260),  # 字/分钟
        "gesture_analysis": {
            "posture_score": round(max(55, min(95, base_score + _RNG.uniform(-8, 8))), 1),
            "gesture_score": round(max(55, min(95, base_score + _RNG.uniform(-10, 6))), 1),
            "eye_contact_score": round(max(55, min(95, base_score + _RNG.uniform(-10, 8))), 1),
        },
        "expression": {
            "smile_ratio": round(_RNG.uniform(0.15, 0.55), 2),
            "voice_energy": round(_RNG.uniform(0.55, 0.95), 2),
        },
        "suggestions": _RNG.sample(_VIDEO_SUGGESTIONS_POOL, k=_RNG.randint(2, 4)),
    }


def _gen_radar_json() -> dict:
    """学生成长画像雷达图"""
    return {
        "lesson_plan": {k: _RNG.randint(68, 92) for k in _LP_DIMENSIONS_KEYS},
        "video": {
            "speech": _RNG.randint(70, 92),
            "gesture": _RNG.randint(65, 88),
            "eye_contact": _RNG.randint(70, 92),
            "expression": _RNG.randint(68, 90),
        },
        "interaction": {
            "response_quality": _RNG.randint(65, 92),
            "openness": _RNG.randint(60, 90),
        },
    }


def _gen_trend_json(num: int = 5, base: float = 75.0) -> list:
    trend = []
    cur = base
    today = datetime.utcnow()
    for i in range(num):
        d = today - timedelta(days=(num - i - 1) * 15)
        cur = max(60.0, min(95.0, cur + _RNG.uniform(-3, 5)))
        trend.append({
            "date": d.strftime("%Y-%m-%d"),
            "total_score": round(cur, 1),
            "lesson_plan_score": round(cur + _RNG.uniform(-3, 3), 1),
            "video_score": round(cur + _RNG.uniform(-4, 4), 1),
        })
    return trend


def _gen_action_items() -> list:
    pool = [
        ("语速控制", 1, "在重点内容处刻意放慢语速并停顿 1–2 秒"),
        ("板书规范", 2, "利用网格纸练习粉笔字，每天 30 分钟"),
        ("提问设计", 1, "设计开放式与评价性问题，替代判断性问题"),
        ("眼神交流", 3, "刻意扫视全场，避免只看前排"),
        ("时间把控", 2, "导入与结尾各控制在 3 分钟内"),
    ]
    picked = _RNG.sample(pool, k=3)
    return [{"dimension": p[0], "priority": p[1], "suggestion": p[2]} for p in picked]


# ============================================================================
# 入口
# ============================================================================

async def seed_rich_demo_data() -> None:
    """富演示数据 seed 主入口。幂等：若 submissions 表非空则跳过所有步骤。"""
    from app.models.submission import Submission

    async with async_session_factory() as session:
        cnt = await session.scalar(select(func.count()).select_from(Submission))
        if (cnt or 0) > 0:
            print(f"ℹ️  富演示数据已存在（submissions={cnt}），跳过 seed_rich_demo_data")
            return

    print("🎨 开始生成富演示数据...")
    await _ensure_teacher_student_grouped()
    tasks_ctx = await _ensure_teacher_tasks()
    await _gen_submissions(tasks_ctx)
    await _gen_notices()
    await _gen_messages()
    await _gen_notifications()
    await _gen_practice_sessions()
    await _gen_ai_call_logs()
    print("🎉 富演示数据生成完成")


# ============================================================================
# 1. 分组：让 teacher / student 纳入活跃批次，和演示学生一起
# ============================================================================

async def _ensure_teacher_student_grouped() -> None:
    """
    将默认账号 teacher（instructor）与 student（student）纳入活跃批次 sem1。
    - teacher 带领 student + S2024001..S2024004 共 5 名学生
    - 若已分组则跳过（避免违反 uq_semester_student）
    """
    from app.models.user import User
    from app.models.semester import Semester, SemesterStatus
    from app.models.group import Group

    async with async_session_factory() as session:
        # 找活跃批次
        sem1 = await session.scalar(
            select(Semester).where(Semester.status == SemesterStatus.ACTIVE).limit(1)
        )
        if sem1 is None:
            print("⚠️  未找到活跃批次，跳过 _ensure_teacher_student_grouped")
            return

        teacher = await session.scalar(select(User).where(User.user_code == "teacher"))
        student = await session.scalar(select(User).where(User.user_code == "student"))
        if not teacher or not student:
            print("⚠️  未找到 teacher / student 默认账号，跳过")
            return

        # 收集 teacher 要带的学生 user_code 列表
        targets = ["student", "S2024001", "S2024002", "S2024003", "S2024004"]
        student_users: List[User] = []
        for code in targets:
            u = await session.scalar(select(User).where(User.user_code == code))
            if u is not None:
                student_users.append(u)

        # 对 targets 中每个学生：若该学生在 sem1 已有分组则跳过，否则绑定到 teacher
        for u in student_users:
            exists = await session.scalar(
                select(Group).where(
                    (Group.semester_id == sem1.id) & (Group.student_id == u.id)
                )
            )
            if exists is None:
                session.add(Group(
                    semester_id=sem1.id,
                    instructor_id=teacher.id,
                    student_id=u.id,
                ))
        await session.commit()
        print(f"✅ teacher 已在活跃批次 {sem1.name} 中绑定 {len(student_users)} 名学生")


# ============================================================================
# 2. teacher 的任务
# ============================================================================

async def _ensure_teacher_tasks() -> Dict[int, List[int]]:
    """
    为默认 teacher 在活跃批次创建 3 个任务（已发布）；
    返回 {semester_id: [task_id,...]} 结构供后续 submission 生成使用。
    同时补充 T001/T002/T003 已经存在的任务一起返回（便于覆盖更多学生）。
    """
    from app.models.user import User
    from app.models.semester import Semester, SemesterStatus
    from app.models.task import Task

    async with async_session_factory() as session:
        sem1 = await session.scalar(
            select(Semester).where(Semester.status == SemesterStatus.ACTIVE).limit(1)
        )
        sem2 = await session.scalar(
            select(Semester).where(Semester.status == SemesterStatus.COMPLETED).limit(1)
        )
        if sem1 is None:
            return {}

        teacher = await session.scalar(select(User).where(User.user_code == "teacher"))
        if teacher is None:
            return {}

        teacher_task_titles = [
            "课堂导入的三种进阶路径（情境/问题/任务）",
            "板书设计实训：结构化与美观并重",
            "课堂提问的梯度化设计与追问技巧",
        ]
        existing_titles = set()
        rows = await session.execute(
            select(Task.title).where(Task.instructor_id == teacher.id)
        )
        for (t,) in rows:
            existing_titles.add(t)

        now = datetime.utcnow()
        added = 0
        for i, title in enumerate(teacher_task_titles):
            if title in existing_titles:
                continue
            session.add(Task(
                title=title,
                content=(
                    f"<h3>任务说明</h3><p>{title}。请录制 10–15 分钟试讲视频并附教案。</p>"
                    "<h4>评分维度</h4><ul>"
                    "<li>教学目标与学情匹配（20%）</li>"
                    "<li>教学过程的逻辑与深度（30%）</li>"
                    "<li>语言与教态（20%）</li>"
                    "<li>板书设计与时间把控（15%）</li>"
                    "<li>创新与互动（15%）</li></ul>"
                ),
                semester_id=sem1.id,
                instructor_id=teacher.id,
                deadline=now + timedelta(days=14 + i * 7),
                require_lesson_plan=True,
                require_video=True,
                is_published=True,
            ))
            added += 1
        await session.commit()
        if added:
            print(f"✅ 为 teacher 账号创建 {added} 个新任务")

        # 返回各 semester 下 已发布的任务 id
        result: Dict[int, List[int]] = {}
        for sem in [s for s in [sem1, sem2] if s is not None]:
            ids = (
                await session.execute(
                    select(Task.id).where(
                        (Task.semester_id == sem.id) & (Task.is_published.is_(True))
                    )
                )
            ).scalars().all()
            result[sem.id] = list(ids)
        return result


# ============================================================================
# 3. Submission 批量生成
# ============================================================================

async def _gen_submissions(tasks_by_sem: Dict[int, List[int]]) -> None:
    """
    对每个 semester 的每个 group (instructor,student)，为该 semester 的每个任务
    以 80% 概率生成一条提交；状态分布 pending 30% / approved 40% / graded 15% / rejected 15%.
    """
    from app.models.submission import Submission, SubmissionStatus
    from app.models.group import Group
    from app.models.task import Task

    if not tasks_by_sem:
        return

    async with async_session_factory() as session:
        total = 0
        now = datetime.utcnow()
        for sem_id, task_ids in tasks_by_sem.items():
            if not task_ids:
                continue
            groups = (await session.execute(
                select(Group).where(Group.semester_id == sem_id)
            )).scalars().all()

            # 预先拉 Task，用来看是否要求 video
            task_map: Dict[int, Task] = {}
            if task_ids:
                rows = (await session.execute(
                    select(Task).where(Task.id.in_(task_ids))
                )).scalars().all()
                task_map = {t.id: t for t in rows}

            for g in groups:
                # 每个学生对该批次的每个任务以 80% 概率生成 submission
                for tid in task_ids:
                    if _RNG.random() > 0.80:
                        continue

                    status_r = _RNG.random()
                    if status_r < 0.30:
                        status = SubmissionStatus.PENDING
                    elif status_r < 0.70:
                        status = SubmissionStatus.APPROVED
                    elif status_r < 0.85:
                        status = SubmissionStatus.GRADED
                    else:
                        status = SubmissionStatus.REJECTED

                    base_score = _RNG.uniform(68, 92)
                    submitted_at = now - timedelta(days=_RNG.randint(1, 40),
                                                   hours=_RNG.randint(0, 23))
                    lp_analysis = _gen_lesson_plan_analysis(base_score)
                    vid_analysis = (
                        _gen_video_analysis(base_score)
                        if task_map.get(tid) and task_map[tid].require_video
                        else None
                    )

                    lp_score = round(lp_analysis["overall_score"], 1)
                    vid_score = round(vid_analysis["overall_score"], 1) if vid_analysis else None
                    total_score = (
                        round((lp_score * 0.4 + (vid_score or lp_score) * 0.6), 1)
                        if status in (SubmissionStatus.APPROVED, SubmissionStatus.GRADED)
                        else None
                    )

                    feedback = None
                    reject_reason = None
                    ai_feedback = (
                        lp_analysis["summary"]
                        + " 视频方面: "
                        + "；".join((vid_analysis or {}).get("suggestions", [])[:2])
                    )
                    ai_score = (
                        round((lp_score * 0.4 + (vid_score or lp_score) * 0.6), 1)
                    )

                    if status == SubmissionStatus.APPROVED:
                        feedback = (
                            "整体完成度较好，教学目标与过程设计符合课标要求；"
                            + _RNG.choice(_LP_HIGHLIGHTS_POOL)
                            + "。继续保持，下次可加强："
                            + _RNG.choice(_LP_SUGGESTIONS_POOL)
                            + "。"
                        )
                    elif status == SubmissionStatus.GRADED:
                        feedback = (
                            "已完成初评，待确认通过。建议重点关注："
                            + "、".join(_RNG.sample(_LP_SUGGESTIONS_POOL, 2))
                            + "。"
                        )
                    elif status == SubmissionStatus.REJECTED:
                        reject_reason = (
                            "本次提交存在以下主要问题：\n"
                            "1) 教学目标表述过于模糊，未使用可观察的行为动词；\n"
                            "2) 教学过程中缺少学生活动与反馈环节；\n"
                            "3) 视频时长不足 " + str(_RNG.randint(5, 9)) + " 分钟，建议重新录制。"
                        )

                    reviewed_at = (
                        submitted_at + timedelta(days=_RNG.randint(1, 5))
                        if status != SubmissionStatus.PENDING else None
                    )

                    sub = Submission(
                        task_id=tid,
                        student_id=g.student_id,
                        lesson_plan_path=f"uploads/demo/lesson_plan_{g.student_id}_{tid}.pdf",
                        lesson_plan_name=f"第{tid}次试讲-教案-{g.student_id}.pdf",
                        video_path=(
                            f"uploads/demo/video_{g.student_id}_{tid}.mp4"
                            if task_map.get(tid) and task_map[tid].require_video
                            else None
                        ),
                        video_name=(
                            f"第{tid}次试讲-视频-{g.student_id}.mp4"
                            if task_map.get(tid) and task_map[tid].require_video
                            else None
                        ),
                        student_remark=_RNG.choice([
                            "本次着重打磨导入环节，期待老师批评指正。",
                            "视频录制了两次，第二版在节奏上有改进。",
                            "这次尝试了情境导入法，请老师多提建议。",
                            "板书还不够熟练，后续会加强练习。",
                            "",
                        ]),
                        status=status,
                        lesson_plan_score=lp_score if total_score is not None else None,
                        video_score=vid_score if total_score is not None else None,
                        total_score=total_score,
                        feedback=feedback,
                        reject_reason=reject_reason,
                        submitted_at=submitted_at,
                        reviewed_at=reviewed_at,
                        submit_count=1 if status != SubmissionStatus.REJECTED else _RNG.randint(1, 2),
                        lesson_plan_analysis=json.dumps(lp_analysis, ensure_ascii=False),
                        video_analysis=(
                            json.dumps(vid_analysis, ensure_ascii=False)
                            if vid_analysis else None
                        ),
                        ai_suggested_feedback=ai_feedback,
                        ai_suggested_score=ai_score,
                    )
                    session.add(sub)
                    total += 1

            await session.commit()
        print(f"✅ 已生成 {total} 条 submission 记录（混合状态）")


# ============================================================================
# 4. 公告 / 消息 / 通知 / 练习会话 / AI 调用日志
# ============================================================================

async def _gen_notices() -> None:
    from app.models.notice import Notice, DisplayType
    from app.models.semester import Semester, SemesterStatus

    async with async_session_factory() as session:
        existing = await session.scalar(select(func.count()).select_from(Notice))
        if (existing or 0) > 0:
            return

        sem1 = await session.scalar(
            select(Semester).where(Semester.status == SemesterStatus.ACTIVE).limit(1)
        )
        for n in _NOTICES:
            dt = n.get("display_type") or "dialog"
            session.add(Notice(
                title=n["title"],
                content=n["content"],
                semester_id=sem1.id if sem1 else None,
                is_pinned=n.get("is_pinned", False),
                is_published=True,
                show_on_login=n.get("show_on_login", False),
                display_type=DisplayType(dt),
            ))
        await session.commit()
        print(f"✅ 已生成 {len(_NOTICES)} 条系统公告")


async def _gen_messages() -> None:
    from app.models.message import Message
    from app.models.user import User
    from app.models.semester import Semester, SemesterStatus

    async with async_session_factory() as session:
        existing = await session.scalar(select(func.count()).select_from(Message))
        if (existing or 0) > 0:
            return

        code_map: Dict[str, Optional[User]] = {}
        for code in ["teacher", "student", "T001", "S2024001", "S2024002"]:
            code_map[code] = await session.scalar(
                select(User).where(User.user_code == code)
            )

        sem1 = await session.scalar(
            select(Semester).where(Semester.status == SemesterStatus.ACTIVE).limit(1)
        )

        now = datetime.utcnow()

        # 主线：teacher ↔ student
        for idx, (from_code, to_code, content) in enumerate(_MESSAGE_THREADS):
            fr = code_map.get(from_code)
            to = code_map.get(to_code)
            if not fr or not to:
                continue
            m = Message(
                sender_id=fr.id,
                receiver_id=to.id,
                semester_id=sem1.id if sem1 else None,
                content=content,
                is_read=idx < len(_MESSAGE_THREADS) - 2,  # 最后两条未读
            )
            m.created_at = now - timedelta(hours=(len(_MESSAGE_THREADS) - idx) * 3)
            session.add(m)

        # 分线：T001 ↔ S2024001/S2024002 各 2 条
        extras = [
            ("T001", "S2024001", "你上次的板书布局比之前更工整了，继续保持！"),
            ("S2024001", "T001", "谢谢老师鼓励，我会加强粉笔字练习。"),
            ("T001", "S2024002", "视频导入环节稍长，建议下次控制在 3 分钟。"),
            ("S2024002", "T001", "收到老师，我重新剪辑后再上传。"),
        ]
        for idx, (fc, tc, content) in enumerate(extras):
            fr = code_map.get(fc)
            to = code_map.get(tc)
            if not fr or not to:
                continue
            m = Message(
                sender_id=fr.id,
                receiver_id=to.id,
                semester_id=sem1.id if sem1 else None,
                content=content,
                is_read=idx % 2 == 0,
            )
            m.created_at = now - timedelta(days=1, hours=idx)
            session.add(m)

        await session.commit()
        print(f"✅ 已生成 {len(_MESSAGE_THREADS) + len(extras)} 条消息")


async def _gen_notifications() -> None:
    from app.models.notification import Notification
    from app.models.user import User, UserRole

    async with async_session_factory() as session:
        existing = await session.scalar(select(func.count()).select_from(Notification))
        if (existing or 0) > 0:
            return

        # 给所有学生 + 默认 teacher 各发一批通知
        students = (await session.execute(
            select(User).where(User.role == UserRole.STUDENT)
        )).scalars().all()
        teacher = await session.scalar(select(User).where(User.user_code == "teacher"))

        now = datetime.utcnow()
        count = 0
        for stu in students:
            for i, (typ, title, content, link) in enumerate(_NOTIFICATIONS):
                n = Notification(
                    user_id=stu.id,
                    type=typ,
                    title=title,
                    content=content,
                    is_read=_RNG.random() < 0.5,
                    link=link,
                )
                n.created_at = now - timedelta(days=_RNG.randint(0, 20),
                                               hours=_RNG.randint(0, 23))
                session.add(n)
                count += 1

        # 给 teacher 一些"有学生提交了作业"的通知
        if teacher:
            for i in range(6):
                n = Notification(
                    user_id=teacher.id,
                    type="task",
                    title="学生提交了新作业",
                    content=f"有 1 名学生提交了《课堂导入的三种进阶路径》的作业，等待你批改。",
                    is_read=_RNG.random() < 0.4,
                    link="/instructor/submissions",
                )
                n.created_at = now - timedelta(days=_RNG.randint(0, 10))
                session.add(n)
                count += 1

        await session.commit()
        print(f"✅ 已生成 {count} 条用户通知")


async def _gen_practice_sessions() -> None:
    from app.models.profile import PracticeSession
    from app.models.user import User, UserRole

    async with async_session_factory() as session:
        existing = await session.scalar(select(func.count()).select_from(PracticeSession))
        if (existing or 0) > 0:
            return

        students = (await session.execute(
            select(User).where(User.role == UserRole.STUDENT)
        )).scalars().all()

        now = datetime.utcnow()
        total = 0
        for stu in students:
            for i in range(_RNG.randint(1, 3)):
                topic, grade, personality = _RNG.choice(_PRACTICE_TOPICS)
                started = now - timedelta(days=_RNG.randint(1, 30),
                                          hours=_RNG.randint(0, 23))
                duration_min = _RNG.randint(10, 25)
                ended = started + timedelta(minutes=duration_min)
                turns = _RNG.randint(6, 18)
                messages = []
                for t in range(turns):
                    if t % 2 == 0:
                        messages.append({"role": "user", "content": f"学生提问 #{t//2+1}"})
                    else:
                        messages.append({"role": "assistant", "content": f"虚拟学生回答 #{(t+1)//2}"})
                rating = round(_RNG.uniform(72, 92), 1)
                report = {
                    "overall_rating": rating,
                    "strengths": _RNG.sample(_LP_HIGHLIGHTS_POOL, 2),
                    "improvements": _RNG.sample(_LP_SUGGESTIONS_POOL, 2),
                    "engagement_score": round(_RNG.uniform(65, 92), 1),
                    "pedagogy_score": round(_RNG.uniform(70, 95), 1),
                }
                session.add(PracticeSession(
                    student_id=stu.id,
                    title=topic,
                    grade=grade,
                    personality=personality,
                    messages_json=json.dumps(messages, ensure_ascii=False),
                    report_json=json.dumps(report, ensure_ascii=False),
                    message_count=turns,
                    overall_rating=rating,
                    started_at=started,
                    ended_at=ended,
                ))
                total += 1
        await session.commit()
        print(f"✅ 已生成 {total} 条备课练习会话记录")


async def _gen_ai_call_logs() -> None:
    from app.models.rubric import AICallLog
    from app.models.user import User

    async with async_session_factory() as session:
        existing = await session.scalar(select(func.count()).select_from(AICallLog))
        if (existing or 0) > 0:
            return

        users = (await session.execute(select(User))).scalars().all()
        if not users:
            return

        now = datetime.utcnow()
        call_types = [
            ("analyze", "qwen-plus"),
            ("video_analyze", "qwen-audio-turbo"),
            ("summary", "qwen-turbo"),
            ("generate", "qwen-plus"),
            ("chat", "qwen-plus"),
            ("improve", "qwen-plus"),
        ]
        providers = ["aliyun", "aliyun", "aliyun", "openai", "aliyun"]
        count = 0
        for _ in range(60):
            u = _RNG.choice(users)
            typ, model = _RNG.choice(call_types)
            log = AICallLog(
                user_id=u.id,
                call_type=typ,
                provider=_RNG.choice(providers),
                model=model,
                input_tokens=_RNG.randint(300, 3000),
                output_tokens=_RNG.randint(200, 2500),
                audio_seconds=(_RNG.uniform(60, 600) if typ == "video_analyze" else 0.0),
                latency_ms=_RNG.randint(400, 4500),
                is_success=_RNG.random() > 0.05,
                request_summary=f"{typ} 调用由 {u.user_code} 触发",
                ip_address=f"192.168.{_RNG.randint(0,3)}.{_RNG.randint(2,254)}",
            )
            log.created_at = now - timedelta(
                days=_RNG.randint(0, 30),
                hours=_RNG.randint(0, 23),
                minutes=_RNG.randint(0, 59),
            )
            session.add(log)
            count += 1
        await session.commit()
        print(f"✅ 已生成 {count} 条 AI 调用日志")

import asyncio
import hashlib
from datetime import timedelta
from types import SimpleNamespace

import httpx
import pytest
import pytest_asyncio
from fastapi import Depends, FastAPI, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.routes import trial_videos, notifications
from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.security import decode_access_token
from app.models.base import Base
from app.models.group import Group
from app.models.semester import Semester, SemesterStatus
from app.models.trial_video import TrialVideo, TrialVideoComment
from app.models.user import User, UserRole
from app.models.notification import Notification
from app.services import trial_videos as service


@pytest_asyncio.fixture
async def environment(tmp_path, monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    for name, value in {
        "TRIAL_VIDEO_STORAGE_DIR": str(tmp_path / "private"), "UPLOAD_DIR": str(tmp_path / "public"),
        "TRIAL_VIDEO_MAX_BYTES": 64, "TRIAL_VIDEO_USER_BYTES": 96,
        "TRIAL_VIDEO_TOTAL_BYTES": 256, "TRIAL_VIDEO_MIN_FREE_BYTES": 0,
        "TRIAL_VIDEO_PRIVATE_DAYS": 15,
    }.items():
        monkeypatch.setattr(service.settings, name, value)
    monkeypatch.setattr(service, "mutation_lock", asyncio.Lock())
    monkeypatch.setattr(service, "async_session_factory", sessions)
    async with sessions() as db:
        for identifier, role in [(1, UserRole.STUDENT), (2, UserRole.STUDENT), (3, UserRole.ADMIN),
                                  (4, UserRole.INSTRUCTOR), (5, UserRole.INSTRUCTOR), (6, UserRole.STUDENT)]:
            db.add(User(id=identifier, user_code=str(identifier), name=f"姓名{identifier}",
                        role=role, password_hash="unused", is_active=True, college=f"学院{identifier}",
                        avatar="/uploads/student-avatar.png" if identifier == 1 else None))
        db.add(Semester(id=1, name="演示批次", status=SemesterStatus.ACTIVE))
        await db.commit()
        db.add(Group(semester_id=1, student_id=1, instructor_id=4))
        await db.commit()

    async def database():
        async with sessions() as db:
            yield db

    async def current_user(request: Request, db=Depends(get_db)):
        identifier = request.headers.get("x-user")
        if identifier not in ("1", "2", "3", "4", "5", "6"):
            raise HTTPException(401, "未登录")
        return await db.get(User, int(identifier))

    async def analysis(identifier):
        async with sessions() as db:
            video = await db.get(TrialVideo, identifier)
            video.analysis_status = "completed"
            video.analysis_result = {"overall_score": 81, "transcript": "仅供本人查看", "suggestions": ["注意停顿"]}
            await db.commit()

    monkeypatch.setattr(service, "analyze_video", analysis)
    app = FastAPI()
    app.include_router(trial_videos.router, prefix="/api/v1/trial-videos")
    app.include_router(notifications.router, prefix="/api/v1/notifications")
    app.dependency_overrides[get_db] = database
    app.dependency_overrides[get_current_user] = current_user
    app.dependency_overrides[notifications.get_current_user] = current_user
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test",
                                 headers={"x-user": "1"}) as client:
        yield client, sessions, tmp_path
    await engine.dispose()


async def upload(client, user="1", content=b"0123456789abcdef", **fields):
    return await client.post("/api/v1/trial-videos/upload", headers={"x-user": user},
        files={"video": ("trial.mp4", content, "video/mp4")},
        data={"title": "牛顿第一定律", "subject": "物理", "is_public": "false", **fields})


async def playback(client, identifier, user="1"):
    return await client.post(f"/api/v1/trial-videos/{identifier}/playback", headers={"x-user": user})


@pytest.mark.asyncio
async def test_private_video_owner_mentor_admin_and_no_public_file_path(environment):
    client, _, root = environment
    options = (await client.get("/api/v1/trial-videos/upload-options")).json()
    assert options["semesters"] == [{"id": 1, "name": "演示批次", "instructor_name": "姓名4"}]
    response = await upload(client)
    assert response.status_code == 201, response.text
    video = response.json()
    assert video["is_public"] is False and video["semester_id"] == 1
    assert video["expires_at"] and video["available"]
    assert "file_name" not in video and "sha256" not in video
    assert not (root / "public").exists()
    assert len(list((root / "private").glob("*.mp4"))) == 1
    for user in ("1", "3", "4"):
        assert (await playback(client, video["id"], user)).status_code == 200
    for user in ("2", "5"):
        assert (await playback(client, video["id"], user)).status_code == 403
        assert (await client.get(f'/api/v1/trial-videos/{video["id"]}/analysis', headers={"x-user": user})).status_code == 403
    assert (await client.get("/api/v1/trial-videos/public", params={"source": "student"})).json()["total"] == 0
    assert (await client.get("/api/v1/trial-videos/instructor", headers={"x-user": "4"})).json()["total"] == 1
    assert (await client.get("/api/v1/trial-videos/instructor", headers={"x-user": "5"})).json()["total"] == 0


@pytest.mark.asyncio
async def test_public_whitelist_range_requests_and_revocation(environment):
    client, _, _ = environment
    video = (await upload(client, is_public="true")).json()
    row = (await client.get("/api/v1/trial-videos/public", params={"source": "student"})).json()["items"][0]
    assert set(row) == {"id", "title", "subject", "description", "author", "college", "can_delete", "presenter_type", "source", "created_at", "published_at"}
    assert row["author"] == "姓名1"
    url = (await playback(client, video["id"], "2")).json()["url"]
    ticket = url.split("ticket=")[1]
    assert decode_access_token(ticket) is None
    response = await client.get(url, headers={"range": "bytes=2-5"})
    assert response.status_code == 206 and response.content == b"2345"
    assert response.headers["content-range"] == "bytes 2-5/16"
    assert (await client.get(url, headers={"range": "bytes=-4"})).content == b"cdef"
    assert (await client.get(url, headers={"range": "bytes=99-"})).status_code == 416
    assert (await client.get(url.replace(ticket, "invalid"))).status_code == 401
    assert (await client.get(f'/api/v1/trial-videos/{video["id"]}/stream')).status_code == 422
    assert (await client.get("/api/v1/trial-videos/public", headers={"x-user": ""})).status_code == 401
    assert (await client.patch(f'/api/v1/trial-videos/{video["id"]}', json={"is_public": False})).status_code == 200
    assert (await client.get(url)).status_code == 403


@pytest.mark.asyncio
async def test_single_personal_site_limits_and_failed_upload_cleanup(environment, monkeypatch):
    client, _, root = environment
    assert (await upload(client, content=b"a" * 65)).status_code == 413
    assert list((root / "private").glob("*")) == []
    assert (await upload(client, content=b"a" * 64)).status_code == 201
    assert (await upload(client, content=b"b" * 33)).status_code == 413
    assert (await upload(client, user="2", content=b"b" * 32)).status_code == 201
    monkeypatch.setattr(service.settings, "TRIAL_VIDEO_TOTAL_BYTES", 100)
    assert (await upload(client, user="3", source="example", presenter_name="张老师", content=b"c" * 8)).status_code == 413
    assert len(list((root / "private").glob("*"))) == 2


@pytest.mark.asyncio
async def test_expiry_releases_capacity_and_keeps_report(environment):
    client, sessions, root = environment
    video = (await upload(client)).json()
    async with sessions() as db:
        record = await db.get(TrialVideo, video["id"])
        record.expires_at = service.now() - timedelta(seconds=1)
        await db.commit()
    assert (await playback(client, video["id"])).status_code == 410
    async with sessions() as db:
        assert await service.cleanup_expired(db) == 1
        await db.commit()
        record = await db.get(TrialVideo, video["id"])
        assert record.file_status == "expired" and record.file_size == 0
        assert record.analysis_result["overall_score"] == 81
    assert not list((root / "private").glob("*"))
    assert (await client.get(f'/api/v1/trial-videos/{video["id"]}/analysis')).json()["analysis"]["overall_score"] == 81
    assert (await client.patch(f'/api/v1/trial-videos/{video["id"]}', json={"is_public": True})).status_code == 410


@pytest.mark.asyncio
async def test_admin_takedown_survives_deletion_and_identical_reupload(environment):
    client, _, _ = environment
    video = (await upload(client, is_public="true")).json()
    endpoint = f'/api/v1/trial-videos/{video["id"]}'
    assert (await client.post(endpoint + "/takedown", json={"reason": "不适合展示"})).status_code == 403
    assert (await client.post(endpoint + "/takedown", headers={"x-user": "3"}, json={"reason": "不适合展示"})).status_code == 200
    assert (await client.patch(endpoint, json={"is_public": True})).status_code == 403
    assert (await client.delete(endpoint)).status_code == 200
    assert (await upload(client, is_public="true")).status_code == 403
    private = await upload(client)
    assert private.status_code == 201 and private.json()["blocked"]
    assert (await client.patch(f'/api/v1/trial-videos/{private.json()["id"]}', json={"is_public": True})).status_code == 403


@pytest.mark.asyncio
async def test_admin_examples_publish_edit_unpublish_delete_and_no_report_leak(environment):
    client, _, _ = environment
    assert (await upload(client, source="example", presenter_name="张老师")).status_code == 403
    response = await upload(client, user="3", source="example", presenter_name="张老师", presenter_type="teacher")
    assert response.status_code == 201, response.text
    video = response.json()
    assert video["is_public"] and video["expires_at"] is None and video["author"] == "张老师"
    assert (await client.get("/api/v1/trial-videos/public")).json()["items"][0]["presenter_type"] == "teacher"
    endpoint = f'/api/v1/trial-videos/{video["id"]}'
    assert (await client.patch(endpoint, json={"title": "改名"})).status_code == 403
    assert (await client.get(endpoint + "/analysis")).status_code == 403
    assert (await client.patch(endpoint, headers={"x-user": "3"}, json={"is_public": False})).status_code == 200
    assert (await playback(client, video["id"])).status_code == 403
    assert (await client.get("/api/v1/trial-videos/public")).json()["total"] == 0
    assert (await client.delete(endpoint, headers={"x-user": "3"})).status_code == 200


@pytest.mark.asyncio
async def test_mentor_changes_revoke_existing_playback_ticket(environment):
    client, sessions, _ = environment
    video = (await upload(client)).json()
    url = (await playback(client, video["id"], "4")).json()["url"]
    async with sessions() as db:
        group = await db.scalar(select(Group).where(Group.student_id == 1))
        group.instructor_id = 5
        await db.commit()
    assert (await client.get(url)).status_code == 403
    assert (await playback(client, video["id"], "5")).status_code == 200


@pytest.mark.asyncio
async def test_upload_metadata_semester_and_concurrent_quota_validation(environment):
    client, sessions, _ = environment
    assert (await upload(client, is_public="true", title=" ")).status_code == 422
    assert (await upload(client, is_public="true", subject="未知学科")).status_code == 422
    assert (await upload(client, semester_id="999")).status_code == 403
    async with sessions() as db:
        db.add(Semester(id=2, name="第二批次", status=SemesterStatus.ACTIVE))
        await db.commit()
    automatic = await upload(client)
    assert automatic.status_code == 201
    assert automatic.json()["semester_id"] == 1
    results = await asyncio.gather(upload(client, semester_id="1", content=b"a" * 64),
                                   upload(client, semester_id="1", content=b"b" * 64))
    assert sorted(response.status_code for response in results) == [201, 413]


@pytest.mark.asyncio
async def test_disk_space_guard_cleans_partial_file(environment, monkeypatch):
    client, _, root = environment
    monkeypatch.setattr(service.shutil, "disk_usage", lambda _: SimpleNamespace(free=0))
    assert (await upload(client)).status_code == 507
    assert list((root / "private").glob("*")) == []
    assert (await client.get("/api/v1/trial-videos/mine")).json()["total"] == 0


@pytest.mark.asyncio
async def test_visibility_changes_set_retention_without_extending_on_metadata_edit(environment):
    client, sessions, _ = environment
    video = (await upload(client)).json()
    endpoint = f'/api/v1/trial-videos/{video["id"]}'
    public = (await client.patch(endpoint, json={"is_public": True})).json()
    assert public["expires_at"] is None and public["is_public"]
    private = (await client.patch(endpoint, json={"is_public": False})).json()
    assert private["expires_at"] is not None
    async with sessions() as db:
        record = await db.get(TrialVideo, video["id"])
        assert timedelta(days=14, hours=23) < record.expires_at - service.now() <= timedelta(days=15)
        record.expires_at = service.now() + timedelta(days=3)
        deadline = record.expires_at
        await db.commit()
    await client.patch(endpoint, json={"description": "修改简介"})
    async with sessions() as db:
        assert (await db.get(TrialVideo, video["id"])).expires_at == deadline


@pytest.mark.asyncio
async def test_interrupted_analysis_marked_failed_without_deleting_video(environment):
    client, sessions, _ = environment
    video = (await upload(client)).json()
    async with sessions() as db:
        record = await db.get(TrialVideo, video["id"])
        record.analysis_status = "processing"
        await db.commit()
    await service.recover_interrupted_analysis()
    report = (await client.get(f'/api/v1/trial-videos/{video["id"]}/analysis')).json()
    assert report["status"] == "failed" and "重启" in report["error"]
    assert report["analysis"]["overall_score"] == 81
    assert (await playback(client, video["id"])).status_code == 200


@pytest.mark.asyncio
async def test_evaluated_upload_reuses_report_and_rejects_mismatches(environment, monkeypatch):
    from app.api.routes.video_analysis import _standalone_analysis_results

    client, sessions, root = environment
    content = b"evaluated trial"
    report = {"overall_score": 91, "transcript": "已完成的评估", "suggestions": []}
    monkeypatch.setitem(_standalone_analysis_results, "evaluated-task", {
        "user_id": 1, "status": "completed", "file_hash": hashlib.sha256(content).hexdigest(),
        "analysis": report,
    })

    async def unexpected_analysis(_identifier):
        pytest.fail("已评估的视频不应再次分析")

    monkeypatch.setattr(service, "analyze_video", unexpected_analysis)
    assert (await upload(client, user="2", content=content, analysis_task_id="evaluated-task")).status_code == 403
    assert (await upload(client, content=b"other video", analysis_task_id="evaluated-task")).status_code == 422
    assert list((root / "private").glob("*")) == []
    response = await upload(client, content=content, analysis_task_id="evaluated-task", is_public="true")
    assert response.status_code == 201, response.text
    assert response.json()["analysis_status"] == "completed"
    async with sessions() as db:
        video = await db.get(TrialVideo, response.json()["id"])
        assert video.analysis_result == report


@pytest.mark.asyncio
async def test_cover_obeys_video_permissions_and_is_deleted_with_video(environment, monkeypatch):
    client, sessions, root = environment
    video = (await upload(client)).json()
    endpoint = f'/api/v1/trial-videos/{video["id"]}'
    async with sessions() as db:
        record = await db.get(TrialVideo, video["id"])
        cover = service.file_path(record).with_suffix(".cover.jpg")
    cover.write_bytes(b"test jpeg")
    assert (await client.get(endpoint + "/cover", headers={"x-user": "2"})).status_code == 403
    assert (await client.get(endpoint + "/cover", headers={"x-user": ""})).status_code == 401
    response = await client.get(endpoint + "/cover")
    assert response.status_code == 200 and response.content == b"test jpeg"
    assert response.headers["content-type"] == "image/jpeg"
    await client.patch(endpoint, json={"is_public": True})
    assert (await client.get(endpoint + "/cover", headers={"x-user": "2"})).status_code == 200
    await client.delete(endpoint)
    assert not cover.exists()
    assert (await client.get(endpoint + "/cover")).status_code == 410


@pytest.mark.asyncio
async def test_cover_falls_back_to_image_when_extraction_is_unavailable(environment, monkeypatch):
    client, _, _ = environment

    def unavailable(*_args, **_kwargs):
        raise FileNotFoundError("ffmpeg")

    monkeypatch.setattr(service.subprocess, "run", unavailable)
    video = (await upload(client, is_public="true")).json()
    response = await client.get(f'/api/v1/trial-videos/{video["id"]}/cover')
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/svg+xml")
    assert "<svg" in response.text


@pytest.mark.asyncio
async def test_upload_defaults_public_and_only_owner_can_delete_from_gallery(environment):
    client, _, _ = environment
    response = await client.post("/api/v1/trial-videos/upload",
        files={"video": ("trial.mp4", b"trial video", "video/mp4")},
        data={"title": "牛顿第一定律", "subject": "物理", "description": "从生活现象理解惯性"})
    assert response.status_code == 201, response.text
    video = response.json()
    assert video["is_public"] is True and video["expires_at"] is None
    gallery = "/api/v1/trial-videos/public?source=student"
    own_card = (await client.get(gallery)).json()["items"][0]
    assert own_card["title"] == "牛顿第一定律"
    assert own_card["description"] == "从生活现象理解惯性"
    assert own_card["author"] == "姓名1" and own_card["college"] == "学院1"
    assert own_card["can_delete"] is True
    peer_card = (await client.get(gallery, headers={"x-user": "2"})).json()["items"][0]
    assert peer_card["can_delete"] is False
    endpoint = f'/api/v1/trial-videos/{video["id"]}'
    assert (await client.delete(endpoint, headers={"x-user": "2"})).status_code == 403
    assert (await client.delete(endpoint)).status_code == 200
    assert (await client.get(gallery)).json()["items"] == []
    assert (await client.get(endpoint + "/analysis")).json()["status"] == "completed"


@pytest.mark.asyncio
async def test_only_students_can_comment_with_persisted_identity_and_pagination(environment):
    client, sessions, _ = environment
    video = (await upload(client, is_public="true")).json()
    endpoint = f'/api/v1/trial-videos/{video["id"]}/comments'
    for identifier in ("1", "2", "1", "2", "1"):
        response = await client.post(endpoint, headers={"x-user": identifier}, json={"content": f"  建议{identifier}\n可以增加课堂提问。  "})
        assert response.status_code == 201, response.text
        row = response.json()
        assert row["content"] == f"建议{identifier}\n可以增加课堂提问。"
        assert row["author_name"] == f"姓名{identifier}" and row["author_role"] == "student"
        assert row["is_video_author"] is (identifier == "1")
        assert row["can_delete"] is True and row["created_at"]
        assert set(row) == {"id", "content", "author_name", "author_role", "is_video_author", "created_at", "can_delete",
                            "parent_id", "reply_count", "is_deleted", "author_avatar"}
    first = (await client.get(endpoint, headers={"x-user": "2"}, params={"page_size": 2})).json()
    assert first["total"] == 5
    assert [row["author_name"] for row in first["items"]] == ["姓名1", "姓名2"]
    assert [row["can_delete"] for row in first["items"]] == [False, True]
    second = (await client.get(endpoint, headers={"x-user": "2"}, params={"page_size": 2, "page": 2})).json()
    assert [row["author_name"] for row in second["items"]] == ["姓名1", "姓名2"]
    assert second["items"][1]["can_delete"] is True
    async with sessions() as db:
        persisted_query = select(TrialVideoComment).where(TrialVideoComment.video_id == video["id"])
        persisted = (await db.scalars(persisted_query)).all()
        assert len(persisted) == 5
        assert {row.author_id for row in persisted} == {1, 2}


@pytest.mark.asyncio
async def test_teachers_cannot_access_comments_but_can_still_watch_videos(environment):
    client, sessions, _ = environment
    video = (await upload(client, is_public="true")).json()
    endpoint = f'/api/v1/trial-videos/{video["id"]}/comments'
    # A historical teacher comment must not grant current comment permissions.
    async with sessions() as db:
        comment = TrialVideoComment(video_id=video["id"], author_id=4, content="历史评论")
        db.add(comment)
        await db.commit()
        comment_id = comment.id
    for identifier in ("4", "5"):
        assert (await playback(client, video["id"], identifier)).status_code == 200
        assert (await client.get(endpoint, headers={"x-user": identifier})).status_code == 403
        assert (await client.post(endpoint, headers={"x-user": identifier}, json={"content": "不应成功"})).status_code == 403
        assert (await client.delete(f"{endpoint}/{comment_id}", headers={"x-user": identifier})).status_code == 403
    assert (await client.post(endpoint, headers={"x-user": "3"}, json={"content": "不应成功"})).status_code == 403
    assert (await client.get(endpoint, headers={"x-user": "3"})).status_code == 200
    assert (await client.delete(f"{endpoint}/{comment_id}", headers={"x-user": "3"})).status_code == 200


@pytest.mark.asyncio
async def test_comment_login_content_validation_and_plain_text(environment):
    client, _, _ = environment
    video = (await upload(client, is_public="true")).json()
    endpoint = f'/api/v1/trial-videos/{video["id"]}/comments'
    assert (await client.get(endpoint, headers={"x-user": ""})).status_code == 401
    assert (await client.post(endpoint, headers={"x-user": ""}, json={"content": "未登录评论"})).status_code == 401
    for content in ("", "   ", "\n\t", "字" * 1001):
        assert (await client.post(endpoint, json={"content": content})).status_code == 422
    assert (await client.post(endpoint, json={"content": "冒用身份", "author_id": 4})).status_code == 422
    text = '<script>alert("test")</script>\n这是纯文本评论。'
    response = await client.post(endpoint, json={"content": text})
    assert response.status_code == 201 and response.json()["content"] == text
    assert (await client.get(endpoint)).json()["total"] == 1
    assert (await client.get(endpoint, params={"page": 0})).status_code == 422
    assert (await client.get(endpoint, params={"page_size": 51})).status_code == 422


@pytest.mark.asyncio
async def test_only_comment_author_or_admin_can_delete_and_ids_are_scoped_to_video(environment):
    client, _, _ = environment
    first_video = (await upload(client, is_public="true")).json()
    second_video = (await upload(client, user="2", is_public="true")).json()
    endpoint = f'/api/v1/trial-videos/{first_video["id"]}/comments'
    comment = (await client.post(endpoint, headers={"x-user": "2"}, json={"content": "同学的建议"})).json()
    delete_url = f'{endpoint}/{comment["id"]}'
    for identifier in ("1", "4", "5"):
        assert (await client.delete(delete_url, headers={"x-user": identifier})).status_code == 403
    assert (await client.delete(delete_url, headers={"x-user": ""})).status_code == 401
    assert (await client.delete(f'/api/v1/trial-videos/{second_video["id"]}/comments/{comment["id"]}', headers={"x-user": "2"})).status_code == 404
    assert (await client.delete(delete_url, headers={"x-user": "2"})).status_code == 200
    assert (await client.get(endpoint)).json()["total"] == 0
    other = (await client.post(endpoint, headers={"x-user": "2"}, json={"content": "同学的反馈"})).json()
    admin_rows = (await client.get(endpoint, headers={"x-user": "3"})).json()["items"]
    assert admin_rows[0]["can_delete"] is True
    assert (await client.delete(f'{endpoint}/{other["id"]}', headers={"x-user": "3"})).status_code == 200
    assert (await client.delete(f'{endpoint}/{other["id"]}', headers={"x-user": "3"})).status_code == 404


@pytest.mark.asyncio
async def test_comment_access_tracks_private_takedown_and_video_deletion(environment):
    client, _, _ = environment
    video = (await upload(client, is_public="true")).json()
    video_url = f'/api/v1/trial-videos/{video["id"]}'
    endpoint = video_url + "/comments"
    assert (await client.post(endpoint, headers={"x-user": "2"}, json={"content": "公开时的评论"})).status_code == 201
    await client.patch(video_url, json={"is_public": False})
    for identifier in ("2", "4", "5"):
        assert (await client.get(endpoint, headers={"x-user": identifier})).status_code == 403
        assert (await client.post(endpoint, headers={"x-user": identifier}, json={"content": "不应成功"})).status_code == 403
    assert (await client.get(endpoint)).status_code == 200
    assert (await client.post(endpoint, json={"content": "本人补充"})).status_code == 201
    assert (await playback(client, video["id"], "4")).status_code == 200
    assert (await client.get(endpoint, headers={"x-user": "3"})).status_code == 200
    await client.post(video_url + "/takedown", headers={"x-user": "3"}, json={"reason": "临时下架"})
    assert (await client.get(endpoint)).status_code == 403
    assert (await client.post(endpoint, json={"content": "不应成功"})).status_code == 403
    await client.delete(video_url)
    assert (await client.get(endpoint)).status_code == 410
    assert (await client.post(endpoint, json={"content": "不应成功"})).status_code == 410


@pytest.mark.asyncio
async def test_students_can_reply_across_multiple_levels_without_losing_threads_to_pagination(environment):
    client, sessions, _ = environment
    video = (await upload(client, is_public="true")).json()
    endpoint = f'/api/v1/trial-videos/{video["id"]}/comments'
    root = (await client.post(endpoint, json={"content": "建议增加提问"})).json()
    replies = []
    for index in range(5):
        response = await client.post(endpoint, headers={"x-user": "2"},
            json={"content": f"同学回复{index}", "parent_id": root["id"]})
        assert response.status_code == 201, response.text
        replies.append(response.json())
    parent = replies[0]
    for level in range(3):
        response = await client.post(endpoint, json={"content": f"继续讨论{level}", "parent_id": parent["id"]})
        assert response.status_code == 201
        parent = response.json()
    roots = (await client.get(endpoint, params={"page_size": 1})).json()
    assert roots["total"] == 1 and roots["comment_count"] == 9
    assert roots["items"][0]["id"] == root["id"]
    assert roots["items"][0]["reply_count"] == 5
    first = (await client.get(endpoint, params={"parent_id": root["id"], "page_size": 3})).json()
    second = (await client.get(endpoint, params={"parent_id": root["id"], "page_size": 3, "page": 2})).json()
    assert first["total"] == 5
    assert [row["id"] for row in first["items"] + second["items"]] == [row["id"] for row in replies]
    assert first["items"][0]["reply_count"] == 1
    assert first["items"][0]["can_delete"] is False
    assert all(row["parent_id"] == root["id"] and row["author_name"] == "姓名2" for row in first["items"])
    async with sessions() as db:
        persisted = await db.get(TrialVideoComment, parent["id"])
        assert persisted.parent_id is not None and persisted.author_id == 1


@pytest.mark.asyncio
async def test_reply_target_validation_and_permissions(environment):
    client, _, _ = environment
    video = (await upload(client, is_public="true")).json()
    other = (await upload(client, user="2", is_public="true")).json()
    endpoint = f'/api/v1/trial-videos/{video["id"]}/comments'
    root = (await client.post(endpoint, json={"content": "原评论"})).json()
    reply_data = {"content": "回复", "parent_id": root["id"]}
    assert (await client.post(f'/api/v1/trial-videos/{other["id"]}/comments', json=reply_data)).status_code == 404
    assert (await client.get(f'/api/v1/trial-videos/{other["id"]}/comments', params={"parent_id": root["id"]})).status_code == 404
    assert (await client.post(endpoint, json={"content": "回复", "parent_id": 99999})).status_code == 404
    for identifier in ("3", "4", "5"):
        assert (await client.post(endpoint, headers={"x-user": identifier}, json=reply_data)).status_code == 403
    for parent_id in (0, -1):
        assert (await client.post(endpoint, json={"content": "回复", "parent_id": parent_id})).status_code == 422
    await client.patch(f'/api/v1/trial-videos/{video["id"]}', json={"is_public": False})
    assert (await client.post(endpoint, headers={"x-user": "2"}, json=reply_data)).status_code == 403
    assert (await client.get(endpoint, headers={"x-user": "2"}, params={"parent_id": root["id"]})).status_code == 403


@pytest.mark.asyncio
async def test_deleting_parent_preserves_classmates_replies_and_prunes_empty_placeholders(environment):
    client, _, _ = environment
    video = (await upload(client, is_public="true")).json()
    endpoint = f'/api/v1/trial-videos/{video["id"]}/comments'
    root = (await client.post(endpoint, json={"content": "原评论"})).json()
    reply = (await client.post(endpoint, headers={"x-user": "2"}, json={"content": "其他同学的回复", "parent_id": root["id"]})).json()
    nested = (await client.post(endpoint, json={"content": "继续回复", "parent_id": reply["id"]})).json()
    assert (await client.delete(f'{endpoint}/{root["id"]}', headers={"x-user": "2"})).status_code == 403
    assert (await client.delete(f'{endpoint}/{root["id"]}')).status_code == 200
    listing = (await client.get(endpoint)).json()
    assert listing["total"] == 1 and listing["comment_count"] == 2
    placeholder = listing["items"][0]
    assert placeholder["is_deleted"] is True and placeholder["content"] == "" and not placeholder["can_delete"]
    assert placeholder["reply_count"] == 1
    assert (await client.get(endpoint, params={"parent_id": root["id"]})).json()["items"][0]["id"] == reply["id"]
    assert (await client.post(endpoint, json={"content": "不能回复已删评论", "parent_id": root["id"]})).status_code == 410
    assert (await client.delete(f'{endpoint}/{root["id"]}')).status_code == 404
    assert (await client.delete(f'{endpoint}/{reply["id"]}', headers={"x-user": "2"})).status_code == 200
    assert (await client.get(endpoint, params={"parent_id": reply["id"]})).json()["items"][0]["id"] == nested["id"]
    assert (await client.delete(f'{endpoint}/{nested["id"]}')).status_code == 200
    assert (await client.get(endpoint)).json()["total"] == 0


@pytest.mark.asyncio
async def test_existing_comment_schema_migration_preserves_rows_and_is_idempotent(tmp_path, monkeypatch):
    from sqlalchemy import text
    from app.core import database

    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "legacy-comments.db"}')
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(database.settings, "DATABASE_URL", "sqlite+aiosqlite:///")
    try:
        async with engine.begin() as connection:
            await connection.execute(text("CREATE TABLE trial_video_comments (id INTEGER PRIMARY KEY, content VARCHAR(1000))"))
            await connection.execute(text("INSERT INTO trial_video_comments (id, content) VALUES (1, '原来的评论')"))
        await database.run_migrations()
        await database.run_migrations()
        async with engine.connect() as connection:
            row = (await connection.execute(text("SELECT content, parent_id, is_deleted FROM trial_video_comments"))).one()
            assert tuple(row) == ("原来的评论", None, 0)
            assert (await connection.execute(text("PRAGMA index_list(trial_video_comments)"))).all()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_comments_and_replies_use_current_account_avatar_without_location(environment):
    client, sessions, _ = environment
    video = (await upload(client, is_public="true")).json()
    endpoint = f'/api/v1/trial-videos/{video["id"]}/comments'
    comment = (await client.post(endpoint, json={"content": "我的评论"})).json()
    assert comment["author_avatar"] == "/uploads/student-avatar.png"
    reply = (await client.post(endpoint, headers={"x-user": "2"},
        json={"content": "同学回复", "parent_id": comment["id"]})).json()
    assert reply["author_avatar"] == "https://api.dicebear.com/7.x/notionists/svg?seed=2&backgroundColor=b6e3f4,c0aede,d1d4f9"
    async with sessions() as db:
        student = await db.get(User, 2)
        student.avatar = "/uploads/new-student-avatar.png"
        await db.commit()
    listing = (await client.get(endpoint, params={"parent_id": comment["id"]})).json()
    assert listing["items"][0]["author_avatar"] == "/uploads/new-student-avatar.png"
    assert listing["items"][0]["created_at"]
    assert not {"ip", "ip_location", "location"} & listing["items"][0].keys()
    assert (await client.post(endpoint, json={"content": "冒用头像", "author_avatar": "/fake.png"})).status_code == 422


@pytest.mark.asyncio
async def test_comment_notifications_target_video_owner_and_reply_author_without_self_or_duplicates(environment):
    client, sessions, _ = environment
    video = (await upload(client, is_public="true")).json()
    endpoint = f'/api/v1/trial-videos/{video["id"]}/comments'
    root = (await client.post(endpoint, headers={"x-user": "2"}, json={"content": "其他同学的评论"})).json()
    await client.post(endpoint, json={"content": "我的补充"})
    response = await client.post(endpoint, headers={"x-user": "6"}, json={"content": "回复其他同学", "parent_id": root["id"]})
    assert response.status_code == 201, response.text
    reply = response.json()
    self_reply = (await client.post(endpoint, headers={"x-user": "2"}, json={"content": "补充自己的意见", "parent_id": root["id"]})).json()
    owner_comment = (await client.post(endpoint, json={"content": "视频作者的评论"})).json()
    same_recipient = (await client.post(endpoint, headers={"x-user": "2"}, json={"content": "回复视频作者", "parent_id": owner_comment["id"]})).json()
    async with sessions() as db:
        records = (await db.scalars(select(Notification).order_by(Notification.id))).all()
        assert len(records) == 5
        assert [row.user_id for row in records] == [1, 1, 2, 1, 1]
        assert all(row.type == "comment" and not row.is_read for row in records)
        assert "回复了你的评论" in records[2].title
        assert records[1].link == records[2].link == f'/student/trial-learning?tab=student&video={video["id"]}&comment={reply["id"]}'
        assert records[0].content == f'《{video["title"]}》\n其他同学的评论'
        assert sum(row.link.endswith(f'comment={same_recipient["id"]}') for row in records) == 1
        assert sum(row.link.endswith(f'comment={self_reply["id"]}') for row in records) == 1


@pytest.mark.asyncio
async def test_comment_notification_read_filters_are_scoped_to_type_and_recipient(environment):
    client, sessions, _ = environment
    video = (await upload(client, is_public="true")).json()
    endpoint = f'/api/v1/trial-videos/{video["id"]}/comments'
    await client.post(endpoint, headers={"x-user": "2"}, json={"content": "新的评论"})
    async with sessions() as db:
        db.add_all([Notification(user_id=1, type="system", title="重要系统通知", content="重要公告"),
                    Notification(user_id=2, type="comment", title="其他人的提醒", content="不属于当前用户")])
        await db.commit()
    base = '/api/v1/notifications'
    listing = (await client.get(base, params={"type": "comment", "is_read": False})).json()["data"]
    assert listing["total"] == 1
    identifier = listing["items"][0]["id"]
    assert (await client.get(base + '/unread-count', params={"type": "comment"})).json()["data"]["count"] == 1
    await client.put(f'{base}/{identifier}/read', headers={"x-user": "2"})
    assert (await client.get(base + '/unread-count', params={"type": "comment"})).json()["data"]["count"] == 1
    await client.put(base + '/read-all', params={"type": "comment"})
    assert (await client.get(base + '/unread-count', params={"type": "comment"})).json()["data"]["count"] == 0
    assert (await client.get(base + '/unread-count', params={"type": "system"})).json()["data"]["count"] == 1
    assert (await client.get(base + '/unread-count', headers={"x-user": "2"}, params={"type": "comment"})).json()["data"]["count"] == 1
    assert (await client.get(base, params={"type": "comment", "is_read": True})).json()["data"]["total"] == 1
    assert (await client.get(base, params={"type": "comment", "is_read": False})).json()["data"]["total"] == 0


@pytest.mark.asyncio
async def test_notification_context_finds_deep_reply_on_older_root_page_and_checks_access(environment):
    client, _, _ = environment
    video = (await upload(client, is_public="true")).json()
    endpoint = f'/api/v1/trial-videos/{video["id"]}/comments'
    root = (await client.post(endpoint, json={"content": "最早的评论"})).json()
    parent = root
    path = [root["id"]]
    for index in range(4):
        parent = (await client.post(endpoint, headers={"x-user": "2"}, json={"content": f"回复{index}", "parent_id": parent["id"]})).json()
        path.append(parent["id"])
    for index in range(21):
        await client.post(endpoint, json={"content": f"新的评论{index}"})
    context_url = f'{endpoint}/{parent["id"]}/context'
    context = (await client.get(context_url, headers={"x-user": "2"})).json()
    assert context["root_page"] == 2
    assert [row["id"] for row in context["thread"]] == path
    assert [row["reply_count"] for row in context["thread"]] == [1, 1, 1, 1, 0]
    detail = (await client.get(f'/api/v1/trial-videos/{video["id"]}', headers={"x-user": "2"})).json()
    assert detail["id"] == video["id"] and "file_name" not in detail
    assert (await client.get(context_url, headers={"x-user": "4"})).status_code == 403
    assert (await client.get(context_url, headers={"x-user": ""})).status_code == 401
    other = (await upload(client, user="2", is_public="true")).json()
    assert (await client.get(f'/api/v1/trial-videos/{other["id"]}/comments/{parent["id"]}/context')).status_code == 404
    await client.delete(f'{endpoint}/{parent["id"]}', headers={"x-user": "2"})
    assert (await client.get(context_url)).status_code == 404
    await client.patch(f'/api/v1/trial-videos/{video["id"]}', json={"is_public": False})
    assert (await client.get(f'{endpoint}/{root["id"]}/context', headers={"x-user": "2"})).status_code == 403
    assert (await client.get(f'/api/v1/trial-videos/{video["id"]}', headers={"x-user": "2"})).status_code == 403


@pytest.mark.asyncio
async def test_examples_missing_and_expired_videos_do_not_accept_comments(environment):
    client, sessions, _ = environment
    example = (await upload(client, user="3", source="example", presenter_name="示范教师")).json()
    endpoint = f'/api/v1/trial-videos/{example["id"]}/comments'
    assert (await client.get(endpoint)).status_code == 422
    assert (await client.post(endpoint, json={"content": "不应成功"})).status_code == 422
    assert (await client.get('/api/v1/trial-videos/99999/comments')).status_code == 404
    video = (await upload(client)).json()
    async with sessions() as db:
        record = await db.get(TrialVideo, video["id"])
        record.expires_at = service.now() - timedelta(seconds=1)
        await db.commit()
    endpoint = f'/api/v1/trial-videos/{video["id"]}/comments'
    assert (await client.get(endpoint)).status_code == 410
    assert (await client.post(endpoint, json={"content": "不应成功"})).status_code == 410

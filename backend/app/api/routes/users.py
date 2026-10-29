"""
User management API routes.
Handles user CRUD and Excel import.
"""
import io
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query, Form
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
import openpyxl

from app.core.database import get_db
from app.core.security import hash_password
from app.core.deps import require_admin
from app.models.user import User, UserRole
from app.schemas.user import (
    UserCreate,
    UserUpdate,
    UserResponse,
    UserImportItem,
    UserImportResult,
    AdminCreate,
)
from app.schemas.common import PageParams, PageResult
from app.utils.excel_handler import create_user_import_template

router = APIRouter()


@router.get(
    "",
    response_model=PageResult[UserResponse],
    summary="获取用户列表",
)
async def get_users(
    role: Optional[UserRole] = Query(None, description="角色筛选"),
    keyword: Optional[str] = Query(None, description="搜索关键词"),
    college: Optional[str] = Query(None, description="学院筛选"),
    major: Optional[str] = Query(None, description="专业筛选"),
    class_name: Optional[str] = Query(None, description="班级筛选"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> PageResult[UserResponse]:
    """获取用户列表，支持角色筛选和关键词搜索。"""
    query = select(User)
    
    if role:
        query = query.where(User.role == role)
    
    if college:
        query = query.where(User.college == college)
    
    if major:
        query = query.where(User.major == major)
    
    if class_name:
        query = query.where(User.class_name == class_name)
    
    if keyword:
        like = f"%{keyword}%"
        query = query.where(
            (User.user_code.ilike(like)) |
            (User.name.ilike(like)) |
            (User.college.ilike(like)) |
            (User.major.ilike(like)) |
            (User.class_name.ilike(like)) |
            (User.head_teacher.ilike(like))
        )
    
    # 获取总数
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query) or 0
    
    # 分页
    query = query.order_by(User.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(query)
    users = result.scalars().all()
    
    return PageResult.create(
        items=[UserResponse.model_validate(u) for u in users],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "",
    response_model=UserResponse,
    summary="创建用户",
)
async def create_user(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> UserResponse:
    """管理员手动创建单个用户。"""
    # 检查工号是否已存在
    existing = await db.execute(
        select(User).where(User.user_code == user_data.user_code)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"工号/学号 {user_data.user_code} 已存在",
        )
    
    # 密码默认为工号
    password = user_data.password or user_data.user_code
    
    user = User(
        user_code=user_data.user_code,
        name=user_data.name,
        role=user_data.role,
        password_hash=hash_password(password),
        is_default_password=True,
        email=user_data.email,
        phone=user_data.phone,
        remark=user_data.remark,
        college=user_data.college,
        major=user_data.major,
        class_name=user_data.class_name,
        head_teacher=user_data.head_teacher,
    )
    
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    return UserResponse.model_validate(user)


@router.post(
    "/import",
    response_model=UserImportResult,
    summary="批量导入用户",
)
async def import_users(
    file: UploadFile = File(..., description="Excel文件"),
    role: Optional[str] = Form(None, description="限制导入的角色类型"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> UserImportResult:
    """
    通过Excel批量导入用户。
    
    Excel格式要求：
    - 第一行为表头：工号/学号、姓名、角色、学院、专业、班级、班主任
      其中学院/专业/班级/班主任为可选列
    - 角色值：admin/instructor/student 或其中文别名
    - 默认密码设为工号
    - role参数：如果指定，则只允许导入该角色的用户
    """
    # 验证文件类型
    if not file.filename or not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请上传Excel文件 (.xlsx 或 .xls)",
        )
    
    # 读取文件内容
    content = await file.read()
    
    try:
        wb = openpyxl.load_workbook(io.BytesIO(content))
        ws = wb.active
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Excel文件读取失败: {str(e)}",
        )
    
    # 跳过表头，解析数据
    success_count = 0
    fail_count = 0
    failed_items = []
    
    # 获取已存在的工号
    existing_codes_result = await db.execute(select(User.user_code))
    existing_codes = {row[0] for row in existing_codes_result.fetchall()}
    
    # 角色映射
    role_map = {
        "admin": UserRole.ADMIN,
        "管理员": UserRole.ADMIN,
        "instructor": UserRole.INSTRUCTOR,
        "老师": UserRole.INSTRUCTOR,
        "教师": UserRole.INSTRUCTOR,
        "指导老师": UserRole.INSTRUCTOR,
        "student": UserRole.STUDENT,
        "学生": UserRole.STUDENT,
    }
    
    # 解析限制角色
    restricted_role = None
    if role:
        restricted_role = role_map.get(role.lower())
        if not restricted_role:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"无效的角色参数: {role}",
            )
    
    new_users = []
    
    for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        if not row or not row[0]:
            continue
        
        try:
            user_code = str(row[0]).strip()
            name = str(row[1]).strip() if len(row) > 1 and row[1] else ""
            role_str = str(row[2]).strip().lower() if len(row) > 2 and row[2] else ""

            college = str(row[3]).strip() if len(row) > 3 and row[3] else None
            major = str(row[4]).strip() if len(row) > 4 and row[4] else None
            class_name = str(row[5]).strip() if len(row) > 5 and row[5] else None
            head_teacher = str(row[6]).strip() if len(row) > 6 and row[6] else None

            # 跳过导入模板中的说明行，避免被计入失败数量
            if (
                user_code.startswith("说明")
                or user_code.startswith("角色可选值")
                or user_code.startswith("默认密码为")
            ):
                continue
            
            # 验证必填字段
            if not user_code or not name or not role_str:
                failed_items.append({
                    "row": row_idx,
                    "data": list(row),
                    "reason": "必填字段缺失",
                })
                fail_count += 1
                continue
            
            # 验证角色
            user_role = role_map.get(role_str)
            if not user_role:
                failed_items.append({
                    "row": row_idx,
                    "data": list(row),
                    "reason": f"无效的角色: {role_str}",
                })
                fail_count += 1
                continue
            
            # 检查角色限制
            if restricted_role and user_role != restricted_role:
                failed_items.append({
                    "row": row_idx,
                    "data": list(row),
                    "reason": f"角色不匹配：当前限制为{restricted_role.value}，但该用户为{user_role.value}",
                })
                fail_count += 1
                continue
            
            # 检查重复
            if user_code in existing_codes:
                failed_items.append({
                    "row": row_idx,
                    "data": list(row),
                    "reason": f"工号/学号已存在: {user_code}",
                })
                fail_count += 1
                continue
            
            # 添加到新用户列表
            new_users.append(User(
                user_code=user_code,
                name=name,
                role=user_role,
                password_hash=hash_password(user_code),  # 默认密码为工号
                is_default_password=True,
                college=college,
                major=major,
                class_name=class_name,
                head_teacher=head_teacher,
            ))
            existing_codes.add(user_code)  # 防止同一文件内重复
            success_count += 1
            
        except Exception as e:
            failed_items.append({
                "row": row_idx,
                "data": list(row) if row else [],
                "reason": str(e),
            })
            fail_count += 1
    
    # 批量插入
    if new_users:
        db.add_all(new_users)
        await db.commit()
    
    return UserImportResult(
        success_count=success_count,
        fail_count=fail_count,
        failed_items=failed_items,
    )


@router.get(
    "/import/template",
    summary="下载用户导入模板",
)
async def download_import_template(
    _: User = Depends(require_admin),
) -> StreamingResponse:
    """下载用户导入的Excel模板文件。"""
    return create_user_import_template()


@router.get(
    "/filter/options",
    summary="获取筛选选项",
)
async def get_filter_options(
    role: Optional[UserRole] = Query(None, description="角色筛选"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    """获取用户筛选的下拉选项（学院、专业、班级等）。"""
    base_query = select(User).where(User.is_active == True)
    if role:
        base_query = base_query.where(User.role == role)
    
    # 获取所有符合条件的用户
    result = await db.execute(base_query)
    users = result.scalars().all()
    
    # 提取唯一值
    colleges = sorted(set(u.college for u in users if u.college))
    majors = sorted(set(u.major for u in users if u.major))
    class_names = sorted(set(u.class_name for u in users if u.class_name))
    head_teachers = sorted(set(u.head_teacher for u in users if u.head_teacher))
    
    return {
        "colleges": colleges,
        "majors": majors,
        "class_names": class_names,
        "head_teachers": head_teachers,
    }


@router.get(
    "/role/{role}",
    response_model=List[UserResponse],
    summary="按角色获取用户列表",
)
async def get_users_by_role(
    role: UserRole,
    active_only: bool = Query(True, description="仅获取启用的用户"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> List[UserResponse]:
    """获取指定角色的所有用户。"""
    query = select(User).where(User.role == role)
    if active_only:
        query = query.where(User.is_active == True)
    
    result = await db.execute(query.order_by(User.user_code))
    users = result.scalars().all()
    
    return [UserResponse.model_validate(u) for u in users]


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    summary="获取用户详情",
)
async def get_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> UserResponse:
    """获取单个用户的详细信息。"""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return UserResponse.model_validate(user)


@router.put(
    "/{user_id}",
    response_model=UserResponse,
    summary="更新用户",
)
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> UserResponse:
    """更新用户信息。"""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    # 更新非空字段
    update_data = user_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)
    
    await db.commit()
    await db.refresh(user)
    
    return UserResponse.model_validate(user)


@router.delete(
    "/{user_id}",
    summary="删除用户",
)
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    """删除用户（软删除，设置is_active=False）。"""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    user.is_active = False
    await db.commit()
    
    return {"message": "用户已禁用"}


@router.post(
    "/{user_id}/reset-password",
    summary="重置用户密码",
)
async def reset_user_password(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    """将用户密码重置为工号。"""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    user.password_hash = hash_password(user.user_code)
    user.is_default_password = True
    await db.commit()
    
    return {"message": "密码已重置为工号"}


@router.delete(
    "/{user_id}/permanent",
    summary="永久删除用户",
)
async def delete_user_permanent(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    """永久删除用户（从数据库中移除）。"""
    from app.models.group import Group
    
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    # 先删除相关的分组记录
    if user.role == UserRole.INSTRUCTOR:
        # 删除作为指导老师的分组
        groups = (await db.execute(select(Group).where(Group.instructor_id == user_id))).scalars().all()
        for group in groups:
            await db.delete(group)
    elif user.role == UserRole.STUDENT:
        # 删除作为学生的分组
        groups = (await db.execute(select(Group).where(Group.student_id == user_id))).scalars().all()
        for group in groups:
            await db.delete(group)
    
    # 删除用户
    await db.delete(user)
    await db.commit()
    
    return {"message": "用户已永久删除"}


@router.post(
    "/admin",
    response_model=UserResponse,
    summary="创建管理员",
)
async def create_admin(
    admin_data: AdminCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> UserResponse:
    """创建新的管理员账号，仅超级管理员可用。"""
    # 检查是否为超级管理员
    if not current_user.is_super_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有超级管理员才能创建管理员账号"
        )
    
    # 检查账号是否已存在
    existing = await db.execute(
        select(User).where(User.user_code == admin_data.user_code)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该账号已存在"
        )
    
    # 创建新管理员
    new_admin = User(
        user_code=admin_data.user_code,
        name=admin_data.name,
        college=admin_data.college,
        role=UserRole.ADMIN,
        password_hash=hash_password(admin_data.password),
        is_default_password=False,  # 使用自定义密码
        is_active=True,
        is_super_admin=False  # 普通管理员
    )
    
    db.add(new_admin)
    await db.commit()
    await db.refresh(new_admin)
    
    return UserResponse.model_validate(new_admin)


@router.get(
    "/export",
    summary="导出用户列表",
)
async def export_users(
    role: Optional[UserRole] = Query(None, description="角色筛选"),
    college: Optional[str] = Query(None, description="学院筛选"),
    major: Optional[str] = Query(None, description="专业筛选"),
    class_name: Optional[str] = Query(None, description="班级筛选"),
    is_active: Optional[bool] = Query(None, description="状态筛选"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> StreamingResponse:
    """导出用户列表为Excel文件。"""
    import io
    import openpyxl
    from openpyxl.styles import Font, Alignment, PatternFill
    
    # 构建查询
    query = select(User).order_by(User.role, User.user_code)
    
    if role:
        query = query.where(User.role == role)
    if college:
        query = query.where(User.college == college)
    if major:
        query = query.where(User.major == major)
    if class_name:
        query = query.where(User.class_name == class_name)
    if is_active is not None:
        query = query.where(User.is_active == is_active)
    
    result = await db.execute(query)
    users = result.scalars().all()
    
    # 创建工作簿
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "用户列表"
    
    # 根据角色设置不同的表头
    if role == UserRole.STUDENT:
        headers = ["序号", "学号", "姓名", "学院", "专业", "班级", "班主任", 
                   "状态", "创建时间"]
    elif role == UserRole.INSTRUCTOR:
        headers = ["序号", "工号", "姓名", "学院", "状态", "创建时间"]
    else:
        headers = ["序号", "工号/学号", "姓名", "角色", "学院", "专业", 
                   "班级", "状态", "创建时间"]
    
    ws.append(headers)
    
    # 设置表头样式
    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True)
    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")
    
    # 角色中文映射
    role_map = {
        "admin": "管理员",
        "instructor": "指导老师",
        "student": "试讲学生"
    }
    
    # 写入数据
    for idx, user in enumerate(users, start=1):
        status = "启用" if user.is_active else "禁用"
        created = user.created_at.strftime("%Y-%m-%d %H:%M:%S") if user.created_at else ""
        
        if role == UserRole.STUDENT:
            ws.append([
                idx,
                user.user_code,
                user.name,
                user.college or "",
                user.major or "",
                user.class_name or "",
                user.head_teacher or "",
                status,
                created
            ])
        elif role == UserRole.INSTRUCTOR:
            ws.append([
                idx,
                user.user_code,
                user.name,
                user.college or "",
                status,
                created
            ])
        else:
            ws.append([
                idx,
                user.user_code,
                user.name,
                role_map.get(user.role.value, user.role.value),
                user.college or "",
                user.major or "",
                user.class_name or "",
                status,
                created
            ])
    
    # 自动调整列宽
    for column in ws.columns:
        max_length = 0
        column_letter = column[0].column_letter
        for cell in column:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        adjusted_width = min(max_length + 2, 50)
        ws.column_dimensions[column_letter].width = adjusted_width
    
    # 保存到字节流
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    
    # 生成文件名
    if role:
        role_name = role_map.get(role.value, role.value)
        filename = f"{role_name}列表.xlsx"
    else:
        filename = "用户列表.xlsx"
    
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"}
    )



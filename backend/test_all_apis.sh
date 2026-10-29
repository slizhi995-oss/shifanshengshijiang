#!/bin/bash
# ============================================================
# 后端 API 全面测试脚本 (基于实际路由)
# ============================================================

BASE="http://localhost:8000/api/v1"
PASS=0
FAIL=0
ERRORS=""

# 获取三个角色的 Token
ADMIN_TOKEN=$(curl -s -X POST "$BASE/auth/login" -H "Content-Type: application/json" \
  -d '{"user_code":"admin","password":"admin123"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

INSTRUCTOR_TOKEN=$(curl -s -X POST "$BASE/auth/login" -H "Content-Type: application/json" \
  -d '{"user_code":"T1000","password":"123456"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

STUDENT_TOKEN=$(curl -s -X POST "$BASE/auth/login" -H "Content-Type: application/json" \
  -d '{"user_code":"S20210000","password":"123456"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

echo "=== Tokens ==="
echo "Admin: ${ADMIN_TOKEN:0:20}..."
echo "Instructor: ${INSTRUCTOR_TOKEN:0:20}..."
echo "Student: ${STUDENT_TOKEN:0:20}..."
echo ""

test_api() {
  local method="$1" url="$2" token="$3" data="$4" desc="$5" expect="${6:-2}"
  local cmd="curl -s -o /tmp/api_resp.json -w '%{http_code}' -X $method '$BASE$url'"
  [ -n "$token" ] && cmd="$cmd -H 'Authorization: Bearer $token'"
  cmd="$cmd -H 'Content-Type: application/json'"
  [ -n "$data" ] && cmd="$cmd -d '$data'"
  local status=$(eval $cmd)
  local body=$(cat /tmp/api_resp.json 2>/dev/null | head -c 200)
  if [[ "$status" == ${expect}* ]]; then
    echo "✅ [$status] $method $url - $desc"
    PASS=$((PASS+1))
  else
    echo "❌ [$status] $method $url - $desc"
    echo "   Response: $body"
    FAIL=$((FAIL+1))
    ERRORS="$ERRORS\n❌ [$status] $method $url - $desc | $body"
  fi
}

echo "============================================"
echo "  1. 健康检查 & 认证"
echo "============================================"
test_api GET "/../health" "" "" "健康检查"
test_api POST "/auth/login" "" '{"user_code":"admin","password":"admin123"}' "管理员登录"
test_api POST "/auth/login" "" '{"user_code":"T1000","password":"123456"}' "导师登录"
test_api POST "/auth/login" "" '{"user_code":"S20210000","password":"123456"}' "学生登录"
test_api POST "/auth/login" "" '{"user_code":"wrong","password":"wrong"}' "错误登录" "4"
test_api GET "/auth/me" "$ADMIN_TOKEN" "" "获取当前用户(管理员)"
test_api GET "/auth/me" "$STUDENT_TOKEN" "" "获取当前用户(学生)"

echo ""
echo "============================================"
echo "  2. 用户管理 (Users)"
echo "============================================"
test_api GET "/users?page=1&page_size=5" "$ADMIN_TOKEN" "" "用户列表"
test_api GET "/users?page=1&page_size=5&role=student" "$ADMIN_TOKEN" "" "学生列表"
test_api GET "/users?page=1&page_size=5&role=instructor" "$ADMIN_TOKEN" "" "导师列表"
test_api GET "/users/role/student" "$ADMIN_TOKEN" "" "按角色获取用户"
test_api GET "/users/filter/options" "$ADMIN_TOKEN" "" "用户筛选选项"
test_api GET "/users/1" "$ADMIN_TOKEN" "" "获取用户详情"
test_api GET "/users/import/template" "$ADMIN_TOKEN" "" "导入模板下载"
test_api GET "/users/export" "$ADMIN_TOKEN" "" "导出用户"

echo ""
echo "============================================"
echo "  3. 批次管理 (Semesters)"
echo "============================================"
test_api GET "/semesters" "$ADMIN_TOKEN" "" "批次列表"
test_api GET "/semesters/active" "$ADMIN_TOKEN" "" "活跃批次"

echo ""
echo "============================================"
echo "  4. 分组分配 (Assignments)"
echo "============================================"
# 先获取一个有效的 semester_id
SEMESTER_ID=$(curl -s "$BASE/semesters" -H "Authorization: Bearer $ADMIN_TOKEN" | python3 -c "
import sys,json
try:
    d=json.load(sys.stdin)
    items=d.get('data',{}).get('items',d.get('data',[]))
    if isinstance(items,list) and len(items)>0:
        print(items[0].get('id',1))
    else:
        print(1)
except: print(1)
")
echo "Using semester_id=$SEMESTER_ID"
test_api GET "/assignments/overview/$SEMESTER_ID" "$ADMIN_TOKEN" "" "分组概览"
test_api GET "/assignments/unassigned/$SEMESTER_ID" "$ADMIN_TOKEN" "" "未分配学生"
test_api GET "/assignments/instructor/$SEMESTER_ID" "$INSTRUCTOR_TOKEN" "" "导师学生列表"
test_api GET "/assignments/filter/options/$SEMESTER_ID" "$ADMIN_TOKEN" "" "分组筛选选项"
test_api GET "/assignments/student/my-instructor/$SEMESTER_ID" "$STUDENT_TOKEN" "" "学生我的导师"
test_api GET "/assignments/import/template" "$ADMIN_TOKEN" "" "分组导入模板"
test_api GET "/assignments/export/$SEMESTER_ID" "$ADMIN_TOKEN" "" "导出分组"

echo ""
echo "============================================"
echo "  5. 任务管理 (Tasks)"
echo "============================================"
test_api GET "/tasks?semester_id=$SEMESTER_ID" "$ADMIN_TOKEN" "" "任务列表"
# 获取一个有效的 task_id
TASK_ID=$(curl -s "$BASE/tasks?semester_id=$SEMESTER_ID" -H "Authorization: Bearer $ADMIN_TOKEN" | python3 -c "
import sys,json
try:
    d=json.load(sys.stdin)
    items=d.get('data',{}).get('items',d.get('data',[]))
    if isinstance(items,list) and len(items)>0:
        print(items[0].get('id',1))
    else:
        print(1)
except: print(1)
")
echo "Using task_id=$TASK_ID"
test_api GET "/tasks/$TASK_ID" "$ADMIN_TOKEN" "" "任务详情"

echo ""
echo "============================================"
echo "  6. 作业提交 (Submissions)"
echo "============================================"
test_api GET "/submissions/my" "$STUDENT_TOKEN" "" "学生我的作业"
test_api GET "/submissions/my/status" "$STUDENT_TOKEN" "" "学生作业状态"
test_api GET "/submissions/instructor?semester_id=$SEMESTER_ID&page=1&page_size=5" "$INSTRUCTOR_TOKEN" "" "导师待批作业"
# 获取一个有效的 submission_id
SUB_ID=$(curl -s "$BASE/submissions/my" -H "Authorization: Bearer $STUDENT_TOKEN" | python3 -c "
import sys,json
try:
    d=json.load(sys.stdin)
    items=d.get('data',{}).get('items',d.get('data',[]))
    if isinstance(items,list) and len(items)>0:
        print(items[0].get('id',1))
    else:
        print(0)
except: print(0)
")
echo "Using submission_id=$SUB_ID"
if [ "$SUB_ID" != "0" ]; then
  test_api GET "/submissions/$SUB_ID" "$STUDENT_TOKEN" "" "作业详情"
  test_api GET "/submissions/$SUB_ID/analysis" "$STUDENT_TOKEN" "" "作业AI分析结果"
fi

echo ""
echo "============================================"
echo "  7. 通知公告 (Notices)"
echo "============================================"
test_api GET "/notices/public/latest" "" "" "最新公告(公开)"
test_api GET "/notices/public/login" "" "" "登录页公告(公开)"
test_api GET "/notices" "$ADMIN_TOKEN" "" "公告列表(管理员)"
test_api GET "/notices/user/unread-count" "$STUDENT_TOKEN" "" "未读公告数"
test_api GET "/notices/user/list" "$STUDENT_TOKEN" "" "用户公告列表"
test_api POST "/notices/user/read-all" "$STUDENT_TOKEN" "" "全部已读"
test_api GET "/notices/admin/read-stats" "$ADMIN_TOKEN" "" "公告阅读统计"

echo ""
echo "============================================"
echo "  8. 消息留言 (Messages)"
echo "============================================"
test_api GET "/messages/contacts" "$STUDENT_TOKEN" "" "联系人列表"
test_api GET "/messages/unread-count" "$STUDENT_TOKEN" "" "未读消息数"
test_api GET "/messages/conversation/10" "$STUDENT_TOKEN" "" "与导师对话"

echo ""
echo "============================================"
echo "  9. 管理员功能 (Admin)"
echo "============================================"
test_api GET "/admin/dashboard" "$ADMIN_TOKEN" "" "管理员仪表盘"
test_api GET "/admin/monitor/$SEMESTER_ID" "$ADMIN_TOKEN" "" "批次监控"
test_api GET "/admin/instructors/$SEMESTER_ID" "$ADMIN_TOKEN" "" "导师列表"

echo ""
echo "============================================"
echo "  10. 系统设置 (System)"
echo "============================================"
test_api GET "/system/settings" "$ADMIN_TOKEN" "" "系统设置"

echo ""
echo "============================================"
echo "  11. 学生成绩 (Grades)"
echo "============================================"
test_api GET "/grades/students?semester_id=$SEMESTER_ID&page=1&page_size=5" "$ADMIN_TOKEN" "" "成绩列表"
test_api GET "/grades/filter-options" "$ADMIN_TOKEN" "" "成绩筛选选项"

echo ""
echo "============================================"
echo "  12. 师生聊天 (Chat)"
echo "============================================"
test_api GET "/chat/contacts" "$STUDENT_TOKEN" "" "聊天联系人"
test_api GET "/chat/unread-count" "$STUDENT_TOKEN" "" "聊天未读数"
test_api GET "/chat/conversations/10" "$STUDENT_TOKEN" "" "聊天记录"

echo ""
echo "============================================"
echo "  13. AI 智能功能 (AI)"
echo "============================================"
test_api GET "/ai/status" "$ADMIN_TOKEN" "" "AI状态"
test_api POST "/ai/summary" "$ADMIN_TOKEN" '{"text":"这是一段测试文本，用于测试AI摘要功能。学生在课堂上表现良好。"}' "AI摘要"
test_api POST "/ai/data-narrative" "$ADMIN_TOKEN" '{"stats":{"total_students":100,"avg_score":85}}' "AI数据叙事"
test_api POST "/ai/knowledge-graph" "$STUDENT_TOKEN" '{"lesson_plan_text":"今天我们学习三角函数的基本概念，包括正弦、余弦和正切函数的定义和性质。"}' "AI知识图谱"
test_api POST "/ai/learning-path" "$STUDENT_TOKEN" '{"student_id":30}' "AI学习路径"
test_api POST "/ai/pre-check" "$STUDENT_TOKEN" '{"lesson_plan_text":"教学目标：学生能够理解三角函数的基本概念"}' "AI预检查"
test_api POST "/ai/assistant/start" "$STUDENT_TOKEN" '{"lesson_plan_text":"今天学习三角函数"}' "AI助手开始会话"
# 获取 session_id 后测试 chat
SESSION_ID=$(curl -s -X POST "$BASE/ai/assistant/start" -H "Authorization: Bearer $STUDENT_TOKEN" -H "Content-Type: application/json" -d '{"lesson_plan_text":"测试教案"}' | python3 -c "
import sys,json
try:
    d=json.load(sys.stdin)
    print(d.get('data',{}).get('session_id',d.get('session_id','')))
except: print('')
")
if [ -n "$SESSION_ID" ]; then
  echo "Using AI session_id=$SESSION_ID"
  test_api POST "/ai/assistant/chat" "$STUDENT_TOKEN" "{\"session_id\":\"$SESSION_ID\",\"message\":\"如何改进教学目标\",\"lesson_plan_text\":\"测试教案\"}" "AI助手对话"
fi

echo ""
echo "============================================"
echo "  14. 视频分析 (Video Analysis)"
echo "============================================"
test_api GET "/video-analysis/usage-stats" "$ADMIN_TOKEN" "" "视频分析使用统计"

echo ""
echo "============================================"
echo "  15. 成长画像 (Profile)"
echo "============================================"
test_api GET "/profile/me" "$STUDENT_TOKEN" "" "学生成长画像"
test_api GET "/profile/overview" "$ADMIN_TOKEN" "" "画像概览"
test_api GET "/profile/students" "$INSTRUCTOR_TOKEN" "" "学生画像列表"

echo ""
echo "============================================"
echo "  16. AI运营看板 (AI Ops)"
echo "============================================"
test_api GET "/admin/ai-ops/overview" "$ADMIN_TOKEN" "" "AI运营概览"
test_api GET "/admin/ai-ops/model-usage" "$ADMIN_TOKEN" "" "AI模型使用"
test_api GET "/admin/ai-ops/failures" "$ADMIN_TOKEN" "" "AI失败记录"
test_api GET "/admin/ai-ops/audit" "$ADMIN_TOKEN" "" "AI审计日志"
test_api GET "/admin/ai-ops/thresholds" "$ADMIN_TOKEN" "" "AI阈值设置"
test_api GET "/admin/ai-ops/status" "$ADMIN_TOKEN" "" "AI服务状态"

echo ""
echo "============================================"
echo "  17. 备课练习会话 (Practice Sessions)"
echo "============================================"
test_api GET "/practice-sessions" "$STUDENT_TOKEN" "" "练习会话列表"
test_api POST "/practice-sessions" "$STUDENT_TOKEN" '{"title":"测试备课","subject":"数学"}' "创建练习会话"
test_api GET "/practice-sessions/stats/me" "$STUDENT_TOKEN" "" "练习统计"

echo ""
echo "============================================"
echo "  18. 数据导出 (Export)"
echo "============================================"
test_api GET "/export/submissions/csv?semester_id=$SEMESTER_ID" "$ADMIN_TOKEN" "" "导出作业CSV"
test_api GET "/export/grades/csv?semester_id=$SEMESTER_ID" "$ADMIN_TOKEN" "" "导出成绩CSV"
test_api GET "/export/semester/$SEMESTER_ID/summary" "$ADMIN_TOKEN" "" "导出批次汇总"

echo ""
echo "============================================"
echo "  19. 统计数据 (Statistics)"
echo "============================================"
test_api GET "/statistics/student/dashboard" "$STUDENT_TOKEN" "" "学生统计仪表盘"
test_api GET "/statistics/instructor/dashboard" "$INSTRUCTOR_TOKEN" "" "导师统计仪表盘"
test_api GET "/statistics/admin/dashboard" "$ADMIN_TOKEN" "" "管理员统计仪表盘"
test_api GET "/statistics/semester/$SEMESTER_ID/summary" "$ADMIN_TOKEN" "" "批次统计汇总"

echo ""
echo "============================================"
echo "  20. 评分规则 (Rubrics)"
echo "============================================"
test_api GET "/rubrics" "$ADMIN_TOKEN" "" "评分规则列表"
test_api GET "/rubrics/defaults" "$ADMIN_TOKEN" "" "默认评分规则"

echo ""
echo "============================================"
echo "  21. 通知中心 (Notifications)"
echo "============================================"
test_api GET "/notifications" "$STUDENT_TOKEN" "" "通知列表"
test_api GET "/notifications/unread-count" "$STUDENT_TOKEN" "" "未读通知数"
test_api PUT "/notifications/read-all" "$STUDENT_TOKEN" "" "全部已读"

echo ""
echo "============================================"
echo "  22. 系统日志 (Logs)"
echo "============================================"
test_api GET "/admin/logs?page=1&page_size=5" "$ADMIN_TOKEN" "" "系统日志"
test_api GET "/admin/logs/statistics" "$ADMIN_TOKEN" "" "日志统计"

echo ""
echo "============================================"
echo "  23. AI模型配置 (AI Model Config)"
echo "============================================"
test_api GET "/admin/ai-models/models" "$ADMIN_TOKEN" "" "AI模型列表"
test_api GET "/admin/ai-models/available-models" "$ADMIN_TOKEN" "" "可用模型列表"
test_api GET "/admin/ai-models/usage-stats" "$ADMIN_TOKEN" "" "模型使用统计"

echo ""
echo "============================================"
echo "  24. 数据大屏 (Data Screen)"
echo "============================================"
test_api GET "/admin/data-screen/overview" "$ADMIN_TOKEN" "" "数据大屏概览"
test_api GET "/admin/data-screen/trends" "$ADMIN_TOKEN" "" "数据趋势"
test_api GET "/admin/data-screen/distribution" "$ADMIN_TOKEN" "" "数据分布"
test_api GET "/admin/data-screen/class-comparison" "$ADMIN_TOKEN" "" "班级对比"

echo ""
echo "============================================"
echo "  25. 导师AI功能 (Instructor AI)"
echo "============================================"
test_api GET "/instructor/class-insights?semester_id=$SEMESTER_ID" "$INSTRUCTOR_TOKEN" "" "班级洞察"

echo ""
echo "============================================"
echo "  26. 管理员AI功能 (Admin AI)"
echo "============================================"
test_api GET "/admin/ai-alerts" "$ADMIN_TOKEN" "" "AI预警"

echo ""
echo "============================================"
echo "        测试结果汇总"
echo "============================================"
TOTAL=$((PASS+FAIL))
echo "总计: $TOTAL 个接口"
echo "✅ 通过: $PASS"
echo "❌ 失败: $FAIL"
echo ""
if [ $FAIL -gt 0 ]; then
  echo "失败详情:"
  echo -e "$ERRORS"
fi

# B 站教学视频检索（教材辅助关键词）

沿用首次实现的检索流程：LLM 读取教案提取视频需求，博查检索 B 站真实视频链接，再由 LLM 按标题和摘要初筛。关联教材的教案额外读取对应小节，补充检索用语。最多展示 3 个候选。不使用逐字引用、必要关键词全命中、评分门槛或必须满足整套实验细节的筛选规则。

## 配置

继续使用被 Git 与 Docker 忽略的 `backend/.env.local`：

```dotenv
BOCHA_API_KEY=填写自己的博查密钥
BOCHA_BASE_URL=https://api.bochaai.com
VIDEO_SEARCH_ENABLED=true
VIDEO_SEARCH_CACHE_HOURS=24
```

复用管理后台默认文本模型。配置顺序为 `.env`、`.env.local`，环境变量优先。不要将真实密钥放入被跟踪的文件。调用用量按 `lesson_video` 记录。

## 检索流程

1. 读取教案；若有明确的教材小节关联，额外提供该小节正文（最多 16000 字符）与最多 16 张已核对图注（每个字段最多 400 字符）。教材补准实验名称、对象和常用术语，教案决定用途和教学环节，不能仅按章节名搜整节讲解，也不能为教案未采用的教材活动另加需求。提取最多 2 个需求，每个最多 2 个简短短语。不要求摘录原文或生成必要词；成功采用教材辅助时，需求附带教材名称、小节等来源说明。
2. 对需求的检索短语去重，一次最多执行 3 个搜索请求。博查请求为 `POST /v1/web-search`，使用原始短语、`include=bilibili.com`、`summary=true`、`freshness=noLimit`、`count=10`。
3. 仅接受 B 站完整 `/video/BV…` 视频页，按 BV 号和分 P 去重；排除 App、文章、搜索列表及其他网站。不抓取网页、不解析短链接、不下载视频。
4. LLM 根据教案需求、视频标题和摘要选最多 3 条相关视频并说明用途。只允许选择已经检索到的 ID，不生成网址。无关结果仍可排除，但不再叠加评分、原文证据、材料/动作逐字命中等硬性门槛。
5. 模型提取失败时退回教案里明确写出的待查找视频；未找到这种占位时按课题查找备课候选。模型筛选不可用时保留真实搜索候选，并标为“搜索候选”，不冒充 AI 已筛选。

教材只从教案已保存的章节 ID 读取，不按课名猜版本，不读取整本教材。关联的历史教材教案须属于当前用户；教材、小节须已发布，学科和年级须相符，来源中保存的书目与章节须一致。无教材、关联失效或未发布时退回原有教案检索。手动输入关键词时直接搜索原词，不调用需求提取模型，也不读取教材。

教案保存后后台检索，不阻塞生成；旧教案在生成页重新打开时自动读取检索状态，必要时启动检索。检索使用独立数据库会话，同次并发通过 run_id 去重，每份教案两次启动至少间隔 30 秒，每用户每分钟最多启动 6 份教案。超过 5 分钟的中断任务可重试。缓存同时包含教案、教材关联及实际输入模型的小节正文和图注；对应内容变化后自动检索失效，手动关键词不受教材正文变化影响。主动检索可刷新，旧策略缓存随版本更新失效。

## 页面与封面

在「AI 教案生成」的 Word 教案下方直接展示推荐候选及之前保存的素材，后台检索完成后自动回显。没有视频结果时不显示视频区，没有音频或视频结果时隐藏整个配套资源区域。生成页仅显示检索结果，不展示关键词表单、空列表或通用技巧推荐。保留已确认的封面及点击标题/封面跳转原视频功能，不使用 iframe。

封面只接受匹配到同一个 BV/分 P 的搜索图片，另外尝试 B 站固定公开元数据接口补充封面和标题。403/412/限流不能误判为删除；未取得封面显示占位，保留原站链接。第一 P 使用标准原站地址，不附加多余的 `p=1`。

推荐仅依据搜索标题与摘要，不表示看过完整视频；需要在 B 站预览确认内容、难度和可播放性。这里保存视频引用，不搬运视频。

## 存储与 API

保留原来的 `lesson_video_searches`、`lesson_videos` 表与接口地址。曾经扩展来源时创建的 `lesson_web_resources` 表及数据保留，不再用于检索和展示，不删除用户数据。

`lesson_id` 是 `AudioLesson.id`，对应生成结果中的 `resource_lesson_id`。接口前缀为 `/api/v1/resources/audio-lessons/{lesson_id}`，全部校验教案所有者。

| 方法 | 后缀 | 功能 |
| --- | --- | --- |
| GET | `/videos` | 检索状态、需求、推荐和已选视频 |
| POST | `/videos/search` | `{query,force}` 提交检索 |
| POST | `/videos` | 按候选 ID 或 `url,title,section,purpose` 保存 B 站引用 |
| DELETE | `/videos/{video_id}` | 删除自己的引用 |
| GET | `/videos/{bvid}/metadata` | 查询本教案 B 站视频的公开元数据 |

## 验证

从 `backend` 目录运行：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_lesson_videos.py tests/test_bilibili_metadata.py tests/test_audio_resources.py tests/test_lesson_resources.py -q --basetemp=outputs/original-video-new-test-dir -p no:cacheprovider
.\.venv\Scripts\python.exe scripts/probe_lesson_videos.py --lesson-id 37 --refresh --output outputs/original-retrieval-restored/oxygen.json
```

自动测试清空真实搜索密钥，使用模拟接口；probe 才调用真实服务，输出不含密钥。根目录的 `scripts/verify_generator_resources_ui.cjs` 使用模拟数据检查桌面和手机上的生成后回显、自动检索及轮询、音频试听下载、候选跳转、已保存视频展示、无结果与错误隐藏、历史恢复及旧链接兼容。`scripts/verify_lesson_videos_ui.cjs` 保留为该验证的兼容入口。默认使用 5173 端口，也可设置 `VIDEO_UI_URL` 指向当前开发服务。

同教案对照实验（会调用真实模型和博查、消耗额度）：

```powershell
.\.venv\Scripts\python.exe scripts/compare_textbook_video_search.py --lesson-id 37 --lesson-id 38 --output-dir outputs/textbook-video-comparison
```

分别运行仅教案与教案加教材的需求提取，后续搜索范围、请求上限与初筛规则相同。相同短语复用搜索响应，阶段结果落盘可续跑；不修改教案和生产推荐缓存。报告同时记录原始返回数、有效视频数和调用错误；不能把超时当作没有相关资源，也不能把候选数量当作相关性评分。推荐仍只基于标题和摘要，未播放核验。

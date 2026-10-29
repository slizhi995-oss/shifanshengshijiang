# 教案 Word 生成与预览

2026-10-17。

AI 教案生成与 AI 备课助手中的教案生成入口统一使用 Word。生成完成后，后端先创建真正的 `.docx` 文件，前端用 `docx-preview` 读取该文件预览；“下载 Word”直接下载已预览的同一份文件。页面不再用正则替换展示教案源文本，也不再提供 Markdown 下载或要求用户解压图片。

## 文件内容

支持中文标题、正文、粗体、列表、教学过程表格、本地教材图片及图注。常见 LaTeX 公式转换为 Word 可编辑的 OMML 公式，包括分数、上下标、根式等。未能识别的公式保留为“公式待核对”文本，防止内容丢失。图片写入 DOCX 包内，下载后不依赖网站登录或外部链接。

使用 A4、黑色标题、宋体正文和有明确边框的表格。清除 Word 默认样式中的主题色和标题下划线，避免不同预览器显示异常。

正文不再输出“教材依据”等来源部分，来源关联仍保存在内部元数据。“教学准备”保留设备、材料和课前任务，删除教材图号、配图清单和插图；实际教学环节仍可展示教材图片。生成提示和历史 Word 转换使用相同规则。

表格列宽按内容分配，表内图片限制在单元格以内；图片等比缩放，最高 10 厘米，短图片导语与图片保持同页，清理旧内容遗留的孤立标点和重复图号。网页教案预览独立滚动，工具栏固定在上方，支持鼠标滚轮和键盘滚动。

## 接口与存储

- `POST /ai/generate` 原有结果字段保留供历史记录和教材配图链路使用，新增 `document_id`、`document_format=docx`、`document_filename`。成功返回前已生成 Word 文件。
- `POST /ai/lesson-documents` 将已有教案转换成 Word，无须再次调用大模型。传入已保存的 `lesson_id` 时校验所有者，并使用服务器保存的正文和教材图片，不使用客户端篡改的图片列表。
- `GET /ai/lesson-documents/{id}` 返回 Word 文件，要求登录，仅所有者可读取，使用私有缓存策略和正式 DOCX MIME 类型。

Word 文件及下载名称元数据保存在 `TEXTBOOK_STORAGE_DIR/word-documents/{user_id}/`，与教材使用相同私有文件卷。备份时同时保留数据库和私有文件卷。新历史记录保存 Word 文档 ID；旧历史记录首次查看时自动转换并保存 ID。文件不存在时允许重新转换。

Word 缓存带排版版本号。读取旧版本时，优先使用本人已保存的教案正文重新生成同一文档；普通教案使用私有元数据中的正文恢复。最早期没有保留正文的普通文档，由页面使用本地历史内容重新转换。

源文本仅用于模型处理和历史兼容，不作为页面展示或用户导出的文件。旧版教材 ZIP 接口保留兼容已有调用方，当前教案页面使用 Word。

不读取模型给出的任意 URL 或本地文件路径。只有所属教案已引用的教材素材可内嵌；普通文本转换中未授权的图片显示待补充提示。

## 验证

```powershell
# backend
.venv\Scripts\python.exe -m pytest tests/test_lesson_word.py tests/test_textbook_pipeline.py tests/test_textbook_auto_images.py -q --basetemp outputs/pytest-word-checked
# frontend
npm run build
# 根目录，前端预览端口5176，使用包含表格、公式、原图的Word验证样本
node scripts/verify_textbook_ui.cjs
```

检查真正的 Word ZIP/OOXML、表格结构、OMML 公式、图片字节、下载文件类型、所有者访问、旧教案转换、旧缓存重建，以及预览与下载字节一致。排版样本及真实长教案通过本机 Microsoft Word 打开并导出 PDF 检查；网页预览检查表格、公式、图片和滚动到文末。

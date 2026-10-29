"""
全量测试数据生成脚本（增强版）
为所有功能模块创建真实且完整的测试数据，确保每个页面、每个字段都有数据展示。

Usage:
    cd backend
    python -m scripts.seed_full_data
"""
import asyncio
import sys
import json
import random
from pathlib import Path
from datetime import date, datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, delete, text
from app.core.database import async_session_factory, engine
from app.core.security import hash_password
from app.models.base import Base
from app.models.user import User, UserRole
from app.models.semester import Semester, SemesterStatus
from app.models.group import Group
from app.models.task import Task
from app.models.submission import Submission, SubmissionStatus
from app.models.notice import Notice, DisplayType
from app.models.notification import Notification
from app.models.message import Message
from app.models.profile import ProfileSnapshot, PracticeSession
from app.models.rubric import GradingRubric, AICallLog


# ==================== 用户数据 ====================
INSTRUCTORS = [
    {"user_code": "T001", "name": "张丽华", "email": "zhanglh@edu.cn", "phone": "13800001001",
     "college": "教育学院", "major": "小学教育", "remark": "副教授，从事小学语文教学研究15年，省级教学名师",
     "avatar": "/avatars/t001.png"},
    {"user_code": "T002", "name": "李明远", "email": "limy@edu.cn", "phone": "13800001002",
     "college": "理学院", "major": "数学与应用数学(师范)", "remark": "讲师，擅长数学课堂教学设计，发表论文20余篇",
     "avatar": "/avatars/t002.png"},
    {"user_code": "T003", "name": "王秀英", "email": "wangxy@edu.cn", "phone": "13800001003",
     "college": "外国语学院", "major": "英语(师范)", "remark": "教授，研究方向为英语教学法，国家级精品课负责人",
     "avatar": "/avatars/t003.png"},
    {"user_code": "T004", "name": "陈国强", "email": "chengq@edu.cn", "phone": "13800001004",
     "college": "教育学院", "major": "学前教育", "remark": "副教授，学前教育教学法专家，主编教材3部",
     "avatar": "/avatars/t004.png"},
]

STUDENTS = [
    {"user_code": "S2021001", "name": "陈思远", "email": "chensy@stu.edu.cn", "phone": "15900001001",
     "college": "教育学院", "major": "小学教育", "class_name": "2021级1班", "head_teacher": "张丽华",
     "avatar": "/avatars/s001.png", "remark": "班长，成绩优秀"},
    {"user_code": "S2021002", "name": "刘雨萱", "email": "liuyx@stu.edu.cn", "phone": "15900001002",
     "college": "教育学院", "major": "小学教育", "class_name": "2021级1班", "head_teacher": "张丽华",
     "avatar": "/avatars/s002.png", "remark": "学习委员"},
    {"user_code": "S2021003", "name": "杨子涵", "email": "yangzh@stu.edu.cn", "phone": "15900001003",
     "college": "文学院", "major": "汉语言文学(师范)", "class_name": "2021级2班", "head_teacher": "李明远",
     "avatar": "/avatars/s003.png", "remark": "文艺委员，普通话一级甲等"},
    {"user_code": "S2021004", "name": "赵博文", "email": "zhaobw@stu.edu.cn", "phone": "15900001004",
     "college": "理学院", "major": "数学与应用数学(师范)", "class_name": "2021级2班", "head_teacher": "李明远",
     "avatar": "/avatars/s004.png", "remark": "数学竞赛获奖"},
    {"user_code": "S2021005", "name": "周诗琪", "email": "zhousq@stu.edu.cn", "phone": "15900001005",
     "college": "外国语学院", "major": "英语(师范)", "class_name": "2021级3班", "head_teacher": "王秀英",
     "avatar": "/avatars/s005.png", "remark": "英语专业四级优秀"},
    {"user_code": "S2021006", "name": "吴浩然", "email": "wuhr@stu.edu.cn", "phone": "15900001006",
     "college": "教育学院", "major": "小学教育", "class_name": "2021级1班", "head_teacher": "张丽华",
     "avatar": "/avatars/s006.png", "remark": "体育特长生"},
    {"user_code": "S2021007", "name": "郑欣怡", "email": "zhengxy@stu.edu.cn", "phone": "15900001007",
     "college": "文学院", "major": "汉语言文学(师范)", "class_name": "2021级2班", "head_teacher": "李明远",
     "avatar": "/avatars/s007.png", "remark": "校报编辑"},
    {"user_code": "S2021008", "name": "孙梓豪", "email": "sunzh@stu.edu.cn", "phone": "15900001008",
     "college": "理学院", "major": "数学与应用数学(师范)", "class_name": "2021级3班", "head_teacher": "王秀英",
     "avatar": "/avatars/s008.png", "remark": ""},
    {"user_code": "S2021009", "name": "马晓燕", "email": "maxy@stu.edu.cn", "phone": "15900001009",
     "college": "教育学院", "major": "学前教育", "class_name": "2022级1班", "head_teacher": "陈国强",
     "avatar": "/avatars/s009.png", "remark": "钢琴十级"},
    {"user_code": "S2021010", "name": "黄宇轩", "email": "huangyx@stu.edu.cn", "phone": "15900001010",
     "college": "教育学院", "major": "小学教育", "class_name": "2022级1班", "head_teacher": "陈国强",
     "avatar": "/avatars/s010.png", "remark": "书法爱好者"},
    {"user_code": "S2021011", "name": "林诗涵", "email": "linsh@stu.edu.cn", "phone": "15900001011",
     "college": "外国语学院", "major": "英语(师范)", "class_name": "2022级2班", "head_teacher": "王秀英",
     "avatar": "/avatars/s011.png", "remark": "辩论队成员"},
    {"user_code": "S2021012", "name": "何子墨", "email": "hezm@stu.edu.cn", "phone": "15900001012",
     "college": "文学院", "major": "汉语言文学(师范)", "class_name": "2021级3班", "head_teacher": "李明远",
     "avatar": "/avatars/s012.png", "remark": "古诗词大赛获奖"},
    {"user_code": "S2021013", "name": "徐佳琪", "email": "xujq@stu.edu.cn", "phone": "15900001013",
     "college": "教育学院", "major": "小学教育", "class_name": "2022级1班", "head_teacher": "陈国强",
     "avatar": "/avatars/s013.png", "remark": "支教志愿者"},
    {"user_code": "S2021014", "name": "高志远", "email": "gaozy@stu.edu.cn", "phone": "15900001014",
     "college": "理学院", "major": "数学与应用数学(师范)", "class_name": "2022级2班", "head_teacher": "李明远",
     "avatar": "/avatars/s014.png", "remark": "编程爱好者"},
    {"user_code": "S2021015", "name": "罗思琪", "email": "luosq@stu.edu.cn", "phone": "15900001015",
     "college": "教育学院", "major": "学前教育", "class_name": "2021级1班", "head_teacher": "张丽华",
     "avatar": "/avatars/s015.png", "remark": "绘画特长"},
    {"user_code": "S2021016", "name": "唐浩宇", "email": "tanghy@stu.edu.cn", "phone": "15900001016",
     "college": "文学院", "major": "汉语言文学(师范)", "class_name": "2022级2班", "head_teacher": "李明远",
     "avatar": "/avatars/s016.png", "remark": "朗诵比赛一等奖"},
    {"user_code": "S2021017", "name": "邓雅文", "email": "dengyw@stu.edu.cn", "phone": "15900001017",
     "college": "外国语学院", "major": "英语(师范)", "class_name": "2021级3班", "head_teacher": "王秀英",
     "avatar": "/avatars/s017.png", "remark": "雅思7.0"},
    {"user_code": "S2021018", "name": "曹俊杰", "email": "caojj@stu.edu.cn", "phone": "15900001018",
     "college": "理学院", "major": "数学与应用数学(师范)", "class_name": "2021级2班", "head_teacher": "李明远",
     "avatar": "/avatars/s018.png", "remark": "数学建模参赛选手"},
    {"user_code": "S2021019", "name": "韩雨欣", "email": "hanyx@stu.edu.cn", "phone": "15900001019",
     "college": "教育学院", "major": "小学教育", "class_name": "2022级1班", "head_teacher": "陈国强",
     "avatar": "/avatars/s019.png", "remark": "心理学辅修"},
    {"user_code": "S2021020", "name": "冯子轩", "email": "fengzx@stu.edu.cn", "phone": "15900001020",
     "college": "教育学院", "major": "小学教育", "class_name": "2022级2班", "head_teacher": "张丽华",
     "avatar": "/avatars/s020.png", "remark": "科技创新大赛获奖"},
]

# ==================== 任务数据 ====================
TASKS_DATA = [
    {
        "title": "小学语文《草原》试讲",
        "content": """<h3>试讲要求</h3>
<p>请围绕部编版小学语文五年级上册《草原》一课，完成一次完整的试讲。</p>
<h4>一、教案要求</h4>
<ul>
<li>使用标准教案模板，包含教学目标（知识与技能、过程与方法、情感态度与价值观）</li>
<li>明确教学重难点，写明重点突破方法</li>
<li>教学过程设计完整（导入→新授→巩固→小结→作业布置）</li>
<li>包含学情分析和教学反思</li>
</ul>
<h4>二、视频要求</h4>
<ul>
<li>时长10-15分钟，展示完整教学片段</li>
<li>画面清晰，声音清楚，建议使用三脚架</li>
<li>注意板书设计的美观性和逻辑性</li>
<li>适当使用多媒体辅助教学</li>
</ul>
<h4>三、评分标准</h4>
<p>教案占40%，视频占60%。重点考查教学目标设定、教学过程设计、课堂互动及语言表达。</p>""",
        "deadline_offset": -15,
        "require_lesson_plan": True,
        "require_video": True,
    },
    {
        "title": "小学数学《三角形内角和》试讲",
        "content": """<h3>试讲要求</h3>
<p>请围绕人教版小学数学四年级下册《三角形内角和》一课，完成试讲。</p>
<h4>一、教案要求</h4>
<ul>
<li>教学目标明确，体现数学核心素养（数学抽象、逻辑推理、数学建模）</li>
<li>设计合理的探究活动，引导学生通过测量、撕拼等方法发现三角形内角和为180°</li>
<li>设计梯度练习，由浅入深</li>
<li>板书设计规范，呈现清晰的知识结构</li>
</ul>
<h4>二、视频要求</h4>
<ul>
<li>时长10-15分钟</li>
<li>注意教具使用和课堂互动演示</li>
<li>语言简洁准确，避免数学术语使用错误</li>
</ul>""",
        "deadline_offset": -5,
        "require_lesson_plan": True,
        "require_video": True,
    },
    {
        "title": "小学英语《My Family》试讲",
        "content": """<h3>Trial Teaching Requirements</h3>
<p>请围绕PEP小学英语三年级上册Unit 2 My Family, Part A Let's learn，完成一次试讲。</p>
<h4>Requirements</h4>
<ul>
<li>Use English as the primary language of instruction (可适当使用中文辅助)</li>
<li>设计趣味性TPR活动和chant，激发学习兴趣</li>
<li>教案中体现分层教学设计和语言操练活动</li>
<li>注意语音语调的准确性和自然性</li>
<li>设计pair work和group work环节</li>
</ul>
<h4>评分重点</h4>
<p>英语口语流利度、课堂活动设计、教学资源运用</p>""",
        "deadline_offset": 3,
        "require_lesson_plan": True,
        "require_video": True,
    },
    {
        "title": "小学科学《种子发芽实验》试讲",
        "content": """<h3>试讲要求</h3>
<p>请围绕教科版小学科学五年级上册《种子发芽实验》，完成试讲。</p>
<ul>
<li>重点展示实验探究环节的教学设计，包括提出问题、作出假设、设计实验、实验操作、得出结论</li>
<li>注意科学术语的准确使用（对照实验、变量控制等）</li>
<li>体现STEM教育理念</li>
<li>本次仅需提交教案，无需录制视频</li>
</ul>
<p><strong>注意</strong>：教案中需包含实验记录单的设计。</p>""",
        "deadline_offset": 8,
        "require_lesson_plan": True,
        "require_video": False,
    },
    {
        "title": "小学数学《分数的初步认识》试讲",
        "content": """<h3>试讲要求</h3>
<p>请围绕人教版三年级上册《分数的初步认识》完成试讲，注意直观教学的运用。</p>
<ul>
<li>准备丰富的教具和学具（圆形纸片、长方形纸条等）</li>
<li>设计动手操作活动，让学生在折叠、涂色中体验分数的含义</li>
<li>从"平均分"引入分数概念，注重概念理解</li>
<li>教案和视频均需提交</li>
<li>视频中需展示学生操作活动的模拟</li>
</ul>""",
        "deadline_offset": 16,
        "require_lesson_plan": True,
        "require_video": True,
    },
    {
        "title": "小学语文《将相和》试讲",
        "content": """<h3>试讲要求</h3>
<p>请围绕部编版五年级下册《将相和》完成试讲。</p>
<ul>
<li>注意人物形象分析的引导方法，抓住关键语句品读</li>
<li>设计有效的课堂讨论环节（小组讨论、角色扮演等）</li>
<li>关注学生阅读策略的培养，如抓关键词、联系上下文理解</li>
<li>渗透中华优秀传统文化教育</li>
</ul>
<p>本课为两课时设计，试讲选取第一课时即可。</p>""",
        "deadline_offset": 22,
        "require_lesson_plan": True,
        "require_video": True,
    },
    {
        "title": "小学道德与法治《我们的班规我们订》试讲",
        "content": """<h3>试讲要求</h3>
<p>请围绕部编版三年级上册《我们的班规我们订》完成试讲。</p>
<ul>
<li>设计情境导入，贴近学生校园生活</li>
<li>体现民主参与意识和规则意识的培养</li>
<li>设计模拟投票、讨论等互动环节</li>
<li>注重德育渗透和价值观引导</li>
</ul>""",
        "deadline_offset": 30,
        "require_lesson_plan": True,
        "require_video": True,
    },
    {
        "title": "小学音乐《让我们荡起双桨》试讲",
        "content": """<h3>试讲要求</h3>
<p>请围绕人音版四年级上册《让我们荡起双桨》完成试讲。</p>
<ul>
<li>教案包含歌曲学唱、节奏训练、音乐欣赏等环节</li>
<li>注意范唱的准确性</li>
<li>设计律动或伴奏活动</li>
<li>仅需提交教案</li>
</ul>""",
        "deadline_offset": 38,
        "require_lesson_plan": True,
        "require_video": False,
    },
]

# ==================== 教师评语库 ====================
FEEDBACKS = [
    "教学设计合理，教学目标明确，三维目标设定准确。重难点把握精准，突破方法有效。板书设计规范美观，教态自然大方。建议在课堂互动环节增加更多开放性提问，关注学生高阶思维的发展。整体完成度较高，继续保持。",
    "教案结构完整，教学过程设计有层次感，从导入到新授再到巩固环节衔接自然流畅。视频中声音清晰，语言表达流畅，普通话标准。建议改进导入环节，可以用更贴近学生生活经验的情境引入，增强学生的参与感。",
    "整体表现优秀！教学目标设计合理且可操作，教学方法多样化（讲授法、讨论法、演示法结合）。注意控制每个环节的时间分配，确保重点内容有足够的讲解和练习时间。导入环节可适当精简。",
    "教学思路清晰，重难点突出。学情分析到位，教学设计符合学生认知水平。建议在巩固练习环节设计分层练习，照顾不同层次学生的需求。板书设计可以更加结构化，建议使用板书框架图。",
    "教案中对学情分析较为充分，教学活动设计有创意，体现了以生为本的教学理念。视频中教态稍显紧张，手势运用不够自然，建议多在镜子前练习，增强自信和感染力。整体完成度较高，是一次不错的尝试。",
    "教学设计注重学生主体地位，探究活动设计合理且具有启发性。课堂提问层次分明，由浅入深。注意课堂语言的规范性，避免口语化表达（如'然后呢''对吧'等口头禅）。评价语言可以更具体、更有针对性。",
    "本次试讲进步明显！教学流程更加顺畅，时间把控也有改善。教具使用恰当，多媒体课件制作精美。建议增加课堂即时评价，多使用鼓励性语言。作业设计可以更加开放和有弹性。",
    "教学目标设定清晰可测，教学重点突出。教案中的教学反思写得很好，说明你对自己的教学有深入思考。视频中板书书写工整，但速度偏慢，建议提前在黑板上标出框架线。总体表现良好。",
]

AI_FEEDBACKS = [
    "AI分析报告：该教案结构完整度评分92/100。教学目标设计符合新课标要求，三维目标表述规范。教学过程中导入环节设计巧妙（得分95），新授环节活动丰富（得分88），但巩固练习环节题量偏少（得分78）。建议在评价环节增加形成性评价的设计，如随堂小测、学生互评等。教案字数2856字，段落结构合理。",
    "AI分析报告：教案整体质量评分87/100。教学重难点把握准确（得分91），教学方法选择恰当（得分85），体现了以学生为中心的教学理念。教学活动设计中操作性活动占比45%，建议增加到50%以上。教案中使用了12个专业术语，术语使用正确率100%。建议增加信息技术手段的运用说明。",
    "AI视频分析报告：语速172字/分钟（标准范围160-200），语速评分89/100。教态评分82/100，站姿端正，但手势运用频率偏低（仅8次/10分钟，建议12-15次）。板书书写评分85/100，字迹工整但排版可优化。课堂互动次数6次/10分钟（建议8-10次），互动评分75/100。眼神交流占比62%（建议70%以上）。总时长11分32秒。",
    "AI分析报告：教案创新性评分78/100。知识准确性评分95/100。教学流程逻辑性评分88/100。发现3处可优化点：(1)导入环节与新课联系不够紧密；(2)小组活动分工说明不够具体；(3)缺少课堂总结的学生参与环节。整体教案质量高于同批次平均水平12%。",
    "AI视频分析报告：语音清晰度评分91/100，普通话标准度评分88/100（发现2处轻声读音偏差）。表情丰富度评分72/100，建议增加微笑频率。讲解节奏评分83/100，重点内容讲解时语速适当放慢（降至150字/分），做得很好。提问等待时间平均4.2秒（建议3-5秒），在合理范围内。",
]

STUDENT_REMARKS = [
    "老师您好，这是我第一次正式的试讲尝试，教案参考了AI助手的建议做了多次修改，希望能得到您的指导。",
    "这次教案我按照标准模板撰写，并结合了课堂观察的心得。视频录了三遍，选了最好的一版提交。",
    "教案中的探究活动部分参考了几位名师的公开课设计，做了一些调整。请老师指正不足之处。",
    "这次试讲我着重改进了上次被指出的导入环节问题，希望有进步。视频中板书设计是提前设计好的。",
    "本次教案写作花了较长时间，特别是在学情分析和教学反思部分做了详细阐述。",
    "老师好！这次我尝试了小组合作学习的教学方式，虽然在模拟过程中有些生硬，但我会继续练习的。",
    "教案使用了AI分析工具进行了优化，视频中尽量做到了语言流畅、教态自然。请老师多提宝贵意见。",
    "这次作业按时完成了，对自己的表现不太满意，特别是时间控制方面，超时了2分钟。下次会注意改进。",
]

REJECT_REASONS = [
    "教案结构不完整，缺少教学反思环节和作业设计部分。请参照模板补充完整后重新提交。教学目标中情感态度与价值观目标表述不够具体。",
    "视频时长不足8分钟，未达到10-15分钟的要求。且视频画面模糊，无法清晰看到板书内容。请重新录制后提交。",
    "教案中教学目标的三维目标表述不规范，重难点分析过于简略。教学过程缺少具体的师生对话设计和预设学生回答。请修改后重交。",
]

# ==================== 消息会话数据 ====================
CONVERSATIONS = [
    [
        ("student", "张老师您好，请问第一次试讲作业的教案格式有什么具体要求吗？我在网上找了好几个模板不确定用哪个。"),
        ("instructor", "你好！教案请使用学院统一模板，我已经在任务详情页附上了模板文件，可以直接下载。模板里各个栏目都有说明，按照要求填写即可。"),
        ("student", "好的收到了！另外想问一下，视频录制可以用手机拍摄吗？还是说需要专业设备？"),
        ("instructor", "手机拍摄就可以，现在手机像素够用了。注意保持画面稳定，建议用三脚架或者找个固定支撑。横屏拍摄，确保光线充足，声音清晰。如果教室里环境嘈杂，可以在安静的房间录制。"),
        ("student", "明白了，谢谢老师！我这周末就开始准备。"),
        ("instructor", "好的，加油！有问题随时问我。建议先把教案写好，然后用系统的AI备课助手模拟一遍再录视频，效果会更好。"),
    ],
    [
        ("student", "李老师，我的《三角形内角和》教案已经写好初稿了，能否帮我先看一下有没有大的问题？"),
        ("instructor", "可以发给我看看。不过我建议你先用系统的AI教案分析功能检查一下，它能对教案结构、目标设定等维度给出详细的分析报告和修改建议。"),
        ("student", "好的我去试试！......老师，AI分析报告出来了，说我的教学目标表述不够具体，探究活动设计缺少学生操作的具体步骤说明。"),
        ("instructor", "AI的分析很到位。教学目标要用可观测、可检测的行为动词，比如'学生能够通过测量和拼合验证三角形内角和为180度'。探究活动要把每个步骤都写清楚，包括给学生几分钟、用什么工具、记录什么。"),
        ("student", "谢谢老师的指导！我按照建议修改后再提交。"),
    ],
    [
        ("student", "王老师好，请问英语试讲需要全程用英语吗？我担心有些地方表述不清楚。"),
        ("instructor", "三年级的英语教学建议以英语为主，关键指令和简单解释用英语。如果涉及比较复杂的文化背景知识或者学生理解有困难的地方，可以适当用中文辅助。大概保持70%以上的英语使用率。"),
        ("student", "好的，我会尽量多用英语。另外TPR活动怎么在视频里呈现呢？我一个人录的话没有学生配合。"),
        ("instructor", "你可以自己示范动作，然后用口头语言模拟学生的反应，比如说'Now stand up, please. Let's do it together.'然后自己做动作。关键是展示你的教学设计意图，不需要真的有学生参与。"),
        ("student", "明白了！I will try my best. Thank you, Ms. Wang!"),
        ("instructor", "Great! I'm looking forward to your performance. Remember to have fun with it!"),
    ],
    [
        ("student", "陈老师您好，我在准备科学实验课教案时遇到了一个问题。对照实验的变量控制部分不太确定怎么向五年级学生解释。"),
        ("instructor", "好问题！对于五年级学生，建议用'公平实验'的概念来替代抽象的'变量控制'。你可以这样引导：要做一个公平的实验，就只能改变一个条件，其他条件都要一样。用具体例子来说明。"),
        ("student", "比如说'我们想研究种子发芽需不需要阳光，就只改变光照这一个条件，水分、温度、土壤都保持一样'，这样表述可以吗？"),
        ("instructor", "非常好！就是这个思路。在教案里你要把学生可能的回答也预设好，这样上课时就能更好地引导讨论。另外实验记录单的设计也很关键，要简洁明了，适合小学生填写。"),
    ],
    [
        ("student", "老师好！第一次作业的成绩出来了，我看到AI分析说我的课堂互动频率偏低，请问怎么改进呢？"),
        ("instructor", "互动频率是很多新手老师的共同问题。建议从以下几点改进：1.每讲3-5分钟设置一个互动点；2.多用提问代替直接讲解；3.设计小组讨论和同伴交流活动；4.除了问答还可以用举手投票、角色扮演等方式互动。"),
        ("student", "明白了，我下次试讲会特别注意这一点。另外AI建议我增加眼神交流，说我62%的时间在看教案，这个比例确实太高了。"),
        ("instructor", "对，理想状态是70%以上的时间看着'学生'方向。可以把教案内容精简成关键词写在小卡片上，减少对教案的依赖。多练习几遍，熟悉教学流程后自然就不需要频繁看教案了。"),
    ],
]

# ==================== 公告数据 ====================
NOTICE_DATA = [
    {
        "title": "欢迎使用师范生试讲智慧管理系统",
        "content": """<p>亲爱的老师和同学们：</p>
<p>欢迎使用高校师范生试讲智慧管理系统！本系统是基于人工智能技术的教学辅助平台，集成了多项AI智能分析功能：</p>
<ul>
<li><strong>AI教案智能分析</strong>：自动分析教案结构完整性、教学目标规范性、教学方法适切性等多个维度，给出具体的改进建议</li>
<li><strong>AI视频诊断分析</strong>：分析试讲视频中的语速、手势频率、眼神交流比例、课堂互动次数等指标，生成可视化报告</li>
<li><strong>AI备课助手</strong>：基于大语言模型的智能助手，可模拟真实课堂情境，帮助师范生在安全环境中反复练习试讲</li>
<li><strong>学生成长画像</strong>：通过多维度数据追踪学习进度，生成个性化能力雷达图和成长趋势分析</li>
<li><strong>AI智能评语</strong>：辅助教师生成专业的评价意见，提高批改效率</li>
</ul>
<p>系统使用指南已上传至帮助中心，如有疑问请联系管理员。</p>
<p>祝大家学习进步！</p>""",
        "is_pinned": True,
        "display_type": DisplayType.DIALOG,
        "show_on_login": True,
    },
    {
        "title": "2025年春季学期试讲安排通知",
        "content": """<p>各位同学：</p>
<p>2025年春季学期试讲训练已正式开始，请注意以下安排：</p>
<ol>
<li>本学期共安排<strong>8次</strong>试讲作业，涵盖语文、数学、英语、科学等学科</li>
<li>每次作业一般包含教案和试讲视频两部分，部分任务仅需提交教案</li>
<li>请在截止日期前完成提交，<strong>逾期将影响平时成绩</strong></li>
<li>提交后系统会自动运行AI分析，24小时内可查看AI分析报告</li>
<li>教师评阅后将收到通知，可在"我的提交"中查看评分和评语</li>
</ol>
<p>本学期评分权重：教案40% + 试讲视频60%</p>
<p>具体任务安排请查看任务看板页面。</p>""",
        "is_pinned": False,
        "display_type": DisplayType.BOTH,
        "show_on_login": False,
    },
    {
        "title": "AI备课助手功能更新公告",
        "content": """<p>同学们好！</p>
<p>AI备课助手已完成重大更新，新增以下功能：</p>
<ul>
<li><strong>虚拟课堂模拟</strong>：支持设置不同性格类型的虚拟学生（活泼型、害羞型、好奇型），模拟真实课堂互动</li>
<li><strong>教案生成</strong>：上传教材内容后，AI可自动生成教案初稿供参考</li>
<li><strong>试讲报告</strong>：每次练习结束后自动生成详细的练习报告，包括语言表达、课堂管理等维度</li>
</ul>
<p>欢迎大家积极使用并反馈使用体验！</p>""",
        "is_pinned": False,
        "display_type": DisplayType.DIALOG,
        "show_on_login": False,
    },
    {
        "title": "系统维护通知 - 本周六凌晨",
        "content": "<p>系统将于本周六（3月15日）凌晨2:00-4:00进行例行维护升级，届时系统将暂停服务。请同学们提前做好安排，避免在维护时段提交作业。维护完成后将新增成绩统计报表功能。</p>",
        "is_pinned": False,
        "display_type": DisplayType.MARQUEE,
        "show_on_login": False,
    },
    {
        "title": "关于视频上传格式的补充说明",
        "content": """<p>近期有同学反映视频上传失败，请注意以下要求：</p>
<ul>
<li>支持格式：MP4、AVI、MOV、WMV</li>
<li>文件大小上限：500MB</li>
<li>建议分辨率：720p及以上</li>
<li>如文件过大，可使用格式工厂等工具压缩后再上传</li>
</ul>
<p>如仍有问题请联系技术支持。</p>""",
        "is_pinned": False,
        "display_type": DisplayType.DIALOG,
        "show_on_login": False,
    },
]


# ==================== 辅助函数 ====================

def make_lesson_plan_analysis(score_base):
    """生成详细的教案AI分析结果"""
    return json.dumps({
        "overall_score": min(100, score_base + random.randint(-3, 5)),
        "structure": {
            "score": min(100, score_base + random.randint(-5, 10)),
            "comment": random.choice([
                "教案结构完整，包含导入、新授、巩固、小结、作业五个环节",
                "教案结构基本完整，建议增加教学反思环节",
                "结构清晰，各环节衔接自然，教学流程设计合理",
            ]),
            "details": {
                "has_objectives": True,
                "has_key_points": True,
                "has_teaching_process": True,
                "has_reflection": random.choice([True, True, False]),
                "has_homework": random.choice([True, True, True, False]),
            }
        },
        "objectives": {
            "score": min(100, score_base + random.randint(-3, 8)),
            "comment": random.choice([
                "三维目标设定准确，行为动词使用规范",
                "教学目标明确，但情感态度目标可更具体",
                "目标设计合理，可操作性强，便于检测",
            ]),
        },
        "methods": {
            "score": min(100, score_base + random.randint(-8, 5)),
            "comment": random.choice([
                "教学方法多样，讲授法、讨论法、演示法结合运用",
                "方法选择恰当，但自主探究活动比例可增加",
                "教学方法适合学生年龄特点，注重了学生参与",
            ]),
        },
        "evaluation": {
            "score": min(100, score_base + random.randint(-12, 3)),
            "comment": random.choice([
                "评价方式以终结性评价为主，建议增加过程性评价",
                "设计了多元评价方式，包括自评、互评、教师评",
                "评价维度较为单一，建议从知识、能力、态度多维度评价",
            ]),
        },
        "innovation": {
            "score": min(100, score_base + random.randint(-15, 5)),
            "comment": random.choice([
                "教学设计有一定创新性，情境设计贴近学生生活",
                "运用了信息技术手段辅助教学，有现代教学意识",
                "教学设计中规中矩，建议尝试更多创新教学方式",
            ]),
        },
        "word_count": random.randint(2200, 3500),
        "paragraph_count": random.randint(15, 30),
        "professional_terms": random.randint(8, 20),
        "analyzed_at": datetime.now().isoformat(),
    }, ensure_ascii=False)


def make_video_analysis(score_base):
    """生成详细的视频AI分析结果"""
    speech_rate = random.randint(145, 230)
    duration = random.randint(540, 960)
    gesture_count = random.randint(5, 25)
    interaction_count = random.randint(2, 15)
    eye_contact_pct = random.randint(45, 85)

    return json.dumps({
        "overall_score": min(100, score_base + random.randint(-5, 5)),
        "duration_seconds": duration,
        "duration_formatted": f"{duration // 60}分{duration % 60}秒",
        "speech": {
            "rate_wpm": speech_rate,
            "rate_score": 90 if 160 <= speech_rate <= 200 else (75 if 140 <= speech_rate <= 220 else 60),
            "clarity_score": min(100, score_base + random.randint(-5, 10)),
            "mandarin_score": min(100, score_base + random.randint(-3, 8)),
            "filler_words_count": random.randint(0, 8),
            "filler_words": random.sample(["嗯", "然后", "就是", "对吧", "那个"], k=random.randint(0, 3)),
            "volume_stability": random.choice(["稳定", "偶有波动", "较为稳定"]),
        },
        "body_language": {
            "posture_score": min(100, score_base + random.randint(-8, 8)),
            "gesture_count": gesture_count,
            "gesture_score": 85 if 12 <= gesture_count <= 20 else (70 if gesture_count >= 8 else 55),
            "movement_pattern": random.choice(["适度走动", "基本站立不动", "走动频繁"]),
            "facial_expression_score": min(100, score_base + random.randint(-10, 5)),
            "smile_frequency": random.choice(["适中", "偏少", "较多"]),
        },
        "interaction": {
            "count": interaction_count,
            "score": 85 if interaction_count >= 8 else (70 if interaction_count >= 5 else 55),
            "question_types": {
                "open_ended": random.randint(1, 5),
                "closed": random.randint(1, 6),
                "rhetorical": random.randint(0, 3),
            },
            "wait_time_avg": round(random.uniform(2.0, 6.0), 1),
            "student_engagement_estimate": random.choice(["高", "中", "较高"]),
        },
        "eye_contact": {
            "percentage": eye_contact_pct,
            "score": 85 if eye_contact_pct >= 70 else (70 if eye_contact_pct >= 55 else 55),
            "looking_at_notes_pct": 100 - eye_contact_pct - random.randint(5, 15),
        },
        "blackboard": {
            "usage_score": min(100, score_base + random.randint(-10, 5)),
            "handwriting_score": min(100, score_base + random.randint(-5, 10)),
            "layout_score": min(100, score_base + random.randint(-8, 8)),
        },
        "time_management": {
            "intro_pct": random.randint(8, 20),
            "main_pct": random.randint(55, 75),
            "practice_pct": random.randint(10, 25),
            "summary_pct": random.randint(3, 10),
            "score": min(100, score_base + random.randint(-8, 8)),
        },
        "analyzed_at": datetime.now().isoformat(),
    }, ensure_ascii=False)


def random_radar_json():
    """生成随机但合理的雷达图数据"""
    base = random.randint(60, 85)
    return json.dumps({
        "lesson_plan": {
            "structure": min(100, base + random.randint(-5, 15)),
            "objectives": min(100, base + random.randint(-3, 12)),
            "methods": min(100, base + random.randint(-8, 10)),
            "evaluation": min(100, base + random.randint(-12, 8)),
            "innovation": min(100, base + random.randint(-10, 10)),
        },
        "video": {
            "speech": min(100, base + random.randint(-5, 12)),
            "gesture": min(100, base + random.randint(-12, 8)),
            "interaction": min(100, base + random.randint(-15, 8)),
            "eye_contact": min(100, base + random.randint(-10, 10)),
            "time_control": min(100, base + random.randint(-8, 12)),
        },
        "overall": {
            "teaching_design": min(100, base + random.randint(-5, 10)),
            "language_expression": min(100, base + random.randint(-8, 12)),
            "blackboard_design": min(100, base + random.randint(-12, 10)),
            "classroom_interaction": min(100, base + random.randint(-15, 8)),
            "teaching_manner": min(100, base + random.randint(-5, 15)),
            "time_management": min(100, base + random.randint(-10, 10)),
        },
    }, ensure_ascii=False)


def random_action_items():
    """生成随机行动建议"""
    all_items = [
        {"dimension": "课堂互动", "priority": 1, "suggestion": "建议增加提问环节，每5分钟至少设置1个互动点，多使用开放性问题引发学生思考", "target_score": 85},
        {"dimension": "语速控制", "priority": 2, "suggestion": "当前语速偏快(210字/分)，建议放慢至160-200字/分，重点内容处可适当停顿", "target_score": 80},
        {"dimension": "板书设计", "priority": 3, "suggestion": "板书层次可以更清晰，建议提前设计板书框架，使用思维导图式板书呈现知识结构", "target_score": 82},
        {"dimension": "时间分配", "priority": 4, "suggestion": "导入环节占比过高(18%)，建议控制在10%以内，将更多时间分配给学生练习环节", "target_score": 78},
        {"dimension": "教态仪表", "priority": 5, "suggestion": "注意与学生的眼神交流(当前62%)，建议达到70%以上。减少看教案频率，多面向学生", "target_score": 85},
        {"dimension": "评价语言", "priority": 6, "suggestion": "课堂评价语言较为单一('很好''对的')，建议使用更具体、更有针对性的评价语", "target_score": 80},
        {"dimension": "教学用语", "priority": 7, "suggestion": "注意减少口头禅('然后''就是说')的使用，语言表达更加规范简练", "target_score": 82},
        {"dimension": "教具运用", "priority": 8, "suggestion": "教具使用频率偏低，建议在关键概念讲解时增加实物演示或多媒体辅助", "target_score": 78},
    ]
    selected = random.sample(all_items, k=random.randint(3, 5))
    for i, item in enumerate(selected):
        item["priority"] = i + 1
    return json.dumps(selected, ensure_ascii=False)


def random_trend_json(count=5):
    """生成随机趋势数据"""
    trend = []
    base_score = random.randint(55, 70)
    for i in range(count):
        d = datetime.now() - timedelta(days=(count - i) * 14)
        base_score = min(98, base_score + random.randint(1, 6))
        lp = min(100, base_score + random.randint(-5, 5))
        vid = min(100, base_score + random.randint(-8, 3))
        trend.append({
            "date": d.strftime("%Y-%m-%d"),
            "task_title": random.choice([t["title"] for t in TASKS_DATA]),
            "total_score": base_score,
            "lesson_plan_score": lp,
            "video_score": vid,
            "ranking": random.randint(1, 15),
            "dimensions": {
                "teaching_design": min(100, base_score + random.randint(-5, 8)),
                "language": min(100, base_score + random.randint(-8, 5)),
                "interaction": min(100, base_score + random.randint(-10, 5)),
            }
        })
    return json.dumps(trend, ensure_ascii=False)


# ==================== 数据库操作 ====================

async def ensure_tables():
    """确保所有表都存在"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("[OK] 数据库表结构已同步")


async def clear_old_data():
    """清除旧的测试数据"""
    async with async_session_factory() as session:
        for model in [AICallLog, PracticeSession, ProfileSnapshot,
                       Notification, Message, Submission, Task,
                       Group, Notice, Semester]:
            try:
                await session.execute(delete(model))
            except Exception:
                await session.rollback()
                continue
        try:
            await session.execute(
                delete(User).where(User.role != UserRole.ADMIN)
            )
        except Exception:
            await session.rollback()
        await session.commit()
    print("[OK] 已清除旧数据")


async def seed_users():
    """创建教师和学生（所有字段填充）"""
    async with async_session_factory() as session:
        instructor_ids = []
        student_ids = []

        for data in INSTRUCTORS:
            user = User(
                user_code=data["user_code"],
                name=data["name"],
                role=UserRole.INSTRUCTOR,
                password_hash=hash_password(data["user_code"]),
                is_default_password=True,
                is_active=True,
                is_super_admin=False,
                email=data["email"],
                phone=data["phone"],
                avatar=data.get("avatar"),
                remark=data.get("remark"),
                college=data.get("college"),
                major=data.get("major"),
                class_name=None,
                head_teacher=None,
            )
            session.add(user)
            await session.flush()
            instructor_ids.append(user.id)

        for data in STUDENTS:
            user = User(
                user_code=data["user_code"],
                name=data["name"],
                role=UserRole.STUDENT,
                password_hash=hash_password(data["user_code"]),
                is_default_password=True,
                is_active=True,
                is_super_admin=False,
                email=data["email"],
                phone=data["phone"],
                avatar=data.get("avatar"),
                remark=data.get("remark", ""),
                college=data.get("college"),
                major=data.get("major"),
                class_name=data.get("class_name"),
                head_teacher=data.get("head_teacher"),
            )
            session.add(user)
            await session.flush()
            student_ids.append(user.id)

        await session.commit()

    print(f"[OK] 创建 {len(INSTRUCTORS)} 位教师, {len(STUDENTS)} 位学生（含email/phone/college/major等全字段）")
    return instructor_ids, student_ids


async def seed_semesters():
    """创建批次（含已完成和进行中）"""
    async with async_session_factory() as session:
        s1 = Semester(
            name="2024秋季试讲训练",
            status=SemesterStatus.COMPLETED,
            start_date=date(2024, 9, 1),
            end_date=date(2025, 1, 15),
            description="2024年秋季学期师范生试讲训练，已于2025年1月15日结束。本批次共完成6轮试讲作业，覆盖语文、数学、英语三个学科。",
        )
        s2 = Semester(
            name="2025春季试讲训练",
            status=SemesterStatus.ACTIVE,
            start_date=date(2025, 2, 17),
            end_date=date(2025, 7, 10),
            description="2025年春季学期师范生试讲训练（进行中）。本批次计划安排8轮试讲作业，新增科学、道法、音乐学科，并引入AI智能分析系统辅助教学评价。",
        )
        s3 = Semester(
            name="2025暑期强化训练",
            status=SemesterStatus.DRAFT,
            start_date=date(2025, 7, 14),
            end_date=date(2025, 8, 30),
            description="2025年暑期师范生试讲强化训练（筹备中），面向需要加强训练的学生。",
        )
        session.add_all([s1, s2, s3])
        await session.flush()
        ids = [s1.id, s2.id, s3.id]
        await session.commit()

    print(f"[OK] 创建 3 个批次（1已完成 + 1进行中 + 1筹备中）")
    return ids


async def seed_groups(semester_ids, instructor_ids, student_ids):
    """分配学生到教师"""
    async with async_session_factory() as session:
        count = 0
        for sem_id in semester_ids[:2]:  # 前两个批次分组
            for i, sid in enumerate(student_ids):
                iid = instructor_ids[i % len(instructor_ids)]
                session.add(Group(
                    semester_id=sem_id,
                    instructor_id=iid,
                    student_id=sid,
                ))
                count += 1
        await session.commit()
    print(f"[OK] 创建 {count} 条分组记录")


async def seed_tasks(semester_ids, instructor_ids):
    """创建任务（所有字段）"""
    task_ids = []
    async with async_session_factory() as session:
        active_sem_id = semester_ids[1]  # 2025春季

        for i, td in enumerate(TASKS_DATA):
            iid = instructor_ids[i % len(instructor_ids)]
            deadline = datetime.now() + timedelta(days=td["deadline_offset"])

            task = Task(
                title=td["title"],
                content=td["content"],
                semester_id=active_sem_id,
                instructor_id=iid,
                deadline=deadline,
                require_lesson_plan=td["require_lesson_plan"],
                require_video=td["require_video"],
                is_published=True,
                attachment_path=f"/uploads/attachments/task_template_{i+1}.docx" if i < 3 else None,
            )
            session.add(task)
            await session.flush()
            task_ids.append(task.id)

        await session.commit()

    print(f"[OK] 创建 {len(TASKS_DATA)} 个任务（含attachment_path）")
    return task_ids


async def seed_submissions(task_ids, student_ids, instructor_ids):
    """创建提交记录（所有字段都填充，各种状态都有）"""
    submission_ids = []
    async with async_session_factory() as session:
        for s_idx, sid in enumerate(student_ids):
            student_name = STUDENTS[s_idx]["name"]

            for t_idx, tid in enumerate(task_ids):
                task_data = TASKS_DATA[t_idx]

                if t_idx == 0:
                    # 任务1（已过期-15天）：所有人都已提交并批改
                    statuses = [SubmissionStatus.APPROVED] * 14 + [SubmissionStatus.REJECTED] * 3 + [SubmissionStatus.GRADED] * 3
                    status = statuses[s_idx % len(statuses)]
                    lp_score = round(random.uniform(68, 96), 1)
                    v_score = round(random.uniform(62, 94), 1)
                    total = round(lp_score * 0.4 + v_score * 0.6, 1)
                    submitted_at = datetime.now() - timedelta(days=random.randint(16, 22), hours=random.randint(1, 20))
                    reviewed_at = datetime.now() - timedelta(days=random.randint(10, 14), hours=random.randint(1, 20))

                    sub = Submission(
                        task_id=tid, student_id=sid,
                        lesson_plan_path=f"/uploads/lesson_plans/semester2_task{tid}_s{sid}.pdf",
                        lesson_plan_name=f"《草原》教案_{student_name}.pdf",
                        video_path=f"/uploads/videos/semester2_task{tid}_s{sid}.mp4",
                        video_name=f"《草原》试讲视频_{student_name}.mp4",
                        student_remark=random.choice(STUDENT_REMARKS),
                        status=status,
                        lesson_plan_score=lp_score, video_score=v_score, total_score=total,
                        feedback=random.choice(FEEDBACKS),
                        reject_reason=random.choice(REJECT_REASONS) if status == SubmissionStatus.REJECTED else None,
                        submitted_at=submitted_at, reviewed_at=reviewed_at,
                        submit_count=random.randint(1, 3),
                        lesson_plan_analysis=make_lesson_plan_analysis(int(lp_score)),
                        video_analysis=make_video_analysis(int(v_score)),
                        ai_suggested_feedback=random.choice(AI_FEEDBACKS),
                        ai_suggested_score=round(total + random.uniform(-5, 5), 1),
                    )
                    session.add(sub)
                    await session.flush()
                    submission_ids.append(sub.id)

                elif t_idx == 1:
                    # 任务2（已过期-5天）：大部分人提交，各种状态
                    if s_idx < 16:
                        status_pool = [SubmissionStatus.APPROVED] * 6 + [SubmissionStatus.PENDING] * 4 + \
                                      [SubmissionStatus.GRADED] * 3 + [SubmissionStatus.REJECTED] * 2
                        status = status_pool[s_idx % len(status_pool)]
                        lp_score = round(random.uniform(70, 95), 1) if status != SubmissionStatus.PENDING else None
                        v_score = round(random.uniform(65, 92), 1) if status != SubmissionStatus.PENDING else None
                        total = round(lp_score * 0.4 + v_score * 0.6, 1) if lp_score and v_score else None
                        submitted_at = datetime.now() - timedelta(days=random.randint(6, 10), hours=random.randint(0, 23))
                        reviewed_at = datetime.now() - timedelta(days=random.randint(1, 4)) if status != SubmissionStatus.PENDING else None

                        sub = Submission(
                            task_id=tid, student_id=sid,
                            lesson_plan_path=f"/uploads/lesson_plans/semester2_task{tid}_s{sid}.pdf",
                            lesson_plan_name=f"《三角形内角和》教案_{student_name}.pdf",
                            video_path=f"/uploads/videos/semester2_task{tid}_s{sid}.mp4",
                            video_name=f"《三角形内角和》试讲_{student_name}.mp4",
                            student_remark=random.choice(STUDENT_REMARKS),
                            status=status,
                            lesson_plan_score=lp_score, video_score=v_score, total_score=total,
                            feedback=random.choice(FEEDBACKS) if status in [SubmissionStatus.GRADED, SubmissionStatus.APPROVED, SubmissionStatus.REJECTED] else None,
                            reject_reason=random.choice(REJECT_REASONS) if status == SubmissionStatus.REJECTED else None,
                            submitted_at=submitted_at, reviewed_at=reviewed_at,
                            submit_count=random.randint(1, 2),
                            lesson_plan_analysis=make_lesson_plan_analysis(int(lp_score)) if lp_score else None,
                            video_analysis=make_video_analysis(int(v_score)) if v_score else None,
                            ai_suggested_feedback=random.choice(AI_FEEDBACKS),
                            ai_suggested_score=round(random.uniform(70, 92), 1),
                        )
                        session.add(sub)
                        await session.flush()
                        submission_ids.append(sub.id)

                elif t_idx == 2:
                    # 任务3（还有3天截止）：部分人提交
                    if s_idx < 10:
                        sub = Submission(
                            task_id=tid, student_id=sid,
                            lesson_plan_path=f"/uploads/lesson_plans/semester2_task{tid}_s{sid}.pdf",
                            lesson_plan_name=f"《My Family》Lesson Plan_{student_name}.pdf",
                            video_path=f"/uploads/videos/semester2_task{tid}_s{sid}.mp4",
                            video_name=f"My Family Trial Teaching_{student_name}.mp4",
                            student_remark=random.choice(STUDENT_REMARKS),
                            status=SubmissionStatus.PENDING,
                            submitted_at=datetime.now() - timedelta(hours=random.randint(2, 72)),
                            submit_count=1,
                            ai_suggested_feedback=random.choice(AI_FEEDBACKS),
                            ai_suggested_score=round(random.uniform(72, 88), 1),
                            lesson_plan_analysis=make_lesson_plan_analysis(random.randint(72, 88)),
                            video_analysis=make_video_analysis(random.randint(68, 85)),
                        )
                        session.add(sub)
                        await session.flush()
                        submission_ids.append(sub.id)

                elif t_idx == 3:
                    # 任务4（仅教案，+8天截止）：少量提交
                    if s_idx < 5:
                        sub = Submission(
                            task_id=tid, student_id=sid,
                            lesson_plan_path=f"/uploads/lesson_plans/semester2_task{tid}_s{sid}.pdf",
                            lesson_plan_name=f"《种子发芽实验》教案_{student_name}.pdf",
                            video_path=None, video_name=None,
                            student_remark=random.choice(STUDENT_REMARKS),
                            status=SubmissionStatus.PENDING,
                            submitted_at=datetime.now() - timedelta(hours=random.randint(1, 48)),
                            submit_count=1,
                            lesson_plan_analysis=make_lesson_plan_analysis(random.randint(70, 90)),
                            ai_suggested_feedback=random.choice(AI_FEEDBACKS),
                            ai_suggested_score=round(random.uniform(70, 88), 1),
                        )
                        session.add(sub)
                        await session.flush()
                        submission_ids.append(sub.id)
                # 任务5-8：未到截止日期，暂无提交

        await session.commit()

    print(f"[OK] 创建 {len(submission_ids)} 条提交记录（含全部字段: scores/feedback/analysis/reject_reason/student_remark等）")
    return submission_ids


async def seed_notices(semester_ids):
    """创建系统公告"""
    async with async_session_factory() as session:
        for i, nd in enumerate(NOTICE_DATA):
            notice = Notice(
                title=nd["title"],
                content=nd["content"],
                is_pinned=nd["is_pinned"],
                is_published=True,
                show_on_login=nd.get("show_on_login", False),
                display_type=nd["display_type"],
                semester_id=semester_ids[1] if i > 0 else None,
                attachment_path="/uploads/notices/user_guide.pdf" if i == 0 else None,
            )
            session.add(notice)
        await session.commit()
    print(f"[OK] 创建 {len(NOTICE_DATA)} 条公告（含attachment_path/show_on_login/display_type）")


async def seed_notifications(student_ids, instructor_ids):
    """创建用户通知"""
    task_titles = [t["title"] for t in TASKS_DATA]

    notif_templates = [
        ("task", "新任务发布", "教师发布了新的试讲任务「{title}」，请及时查看任务要求并在截止日期前完成提交。", "/student/tasks"),
        ("grade", "作业已批改", "您提交的「{title}」已被教师批改，获得{score}分。请查看详细评分和改进建议。", "/student/my-submissions"),
        ("ai", "AI分析完成", "您提交的「{title}」的AI分析报告已生成，包含教案结构分析和视频诊断数据，快去查看！", "/student/my-submissions"),
        ("system", "截止提醒", "距离「{title}」截止还有3天，您尚未提交，请尽快完成。", "/student/tasks"),
        ("message", "新消息", "您的指导教师给您发送了一条新消息，请查看。", "/student/messages"),
    ]

    async with async_session_factory() as session:
        count = 0
        for sid in student_ids:
            for ntype, ntitle, template, link in notif_templates:
                title = random.choice(task_titles)
                score = round(random.uniform(72, 95), 1)
                content = template.format(title=title, score=score)
                notif = Notification(
                    user_id=sid,
                    type=ntype,
                    title=ntitle,
                    content=content,
                    is_read=random.choice([True, True, False]),
                    link=link,
                    submission_id=random.randint(1, 50) if ntype in ["grade", "ai"] else None,
                )
                session.add(notif)
                count += 1

        # 教师通知
        for iid in instructor_ids:
            for _ in range(5):
                student_name = random.choice(STUDENTS)["name"]
                task_title = random.choice(task_titles)
                ntype = random.choice(["grade", "task", "ai", "system"])
                if ntype == "grade":
                    notif = Notification(user_id=iid, type="grade", title="新的作业提交",
                        content=f"学生{student_name}提交了「{task_title}」的作业，请及时批改。",
                        is_read=random.choice([True, False]), link="/instructor/submissions")
                elif ntype == "ai":
                    notif = Notification(user_id=iid, type="ai", title="AI分析完成",
                        content=f"学生{student_name}的「{task_title}」AI分析报告已生成，可作为评分参考。",
                        is_read=random.choice([True, False]), link="/instructor/submissions")
                else:
                    notif = Notification(user_id=iid, type="system", title="批改提醒",
                        content=f"您有{random.randint(2, 8)}份待批改的作业，请尽快完成评阅。",
                        is_read=random.choice([True, False]), link="/instructor/submissions")
                session.add(notif)
                count += 1

        await session.commit()
    print(f"[OK] 创建 {count} 条通知（含type/link/submission_id等全字段）")


async def seed_messages(semester_ids, student_ids, instructor_ids):
    """创建师生消息（多轮对话）"""
    async with async_session_factory() as session:
        count = 0
        for conv_idx, conversation in enumerate(CONVERSATIONS):
            if conv_idx >= len(student_ids):
                break
            sid = student_ids[conv_idx]
            iid = instructor_ids[conv_idx % len(instructor_ids)]

            for m_idx, (role, content) in enumerate(conversation):
                sender = sid if role == "student" else iid
                receiver = iid if role == "student" else sid

                msg = Message(
                    sender_id=sender,
                    receiver_id=receiver,
                    semester_id=semester_ids[1],
                    content=content,
                    is_read=m_idx < len(conversation) - 1,
                )
                session.add(msg)
                count += 1

        # 额外给更多学生创建一些简短对话
        short_msgs = [
            ("student", "老师好，请问作业截止日期可以延期吗？"),
            ("instructor", "原则上不延期，如果有特殊情况可以提前跟我说明。"),
            ("student", "好的，我会按时提交的，谢谢老师。"),
        ]
        for s_idx in range(5, min(15, len(student_ids))):
            sid = student_ids[s_idx]
            iid = instructor_ids[s_idx % len(instructor_ids)]
            for m_idx, (role, content) in enumerate(short_msgs):
                sender = sid if role == "student" else iid
                receiver = iid if role == "student" else sid
                msg = Message(
                    sender_id=sender, receiver_id=receiver,
                    semester_id=semester_ids[1], content=content,
                    is_read=True,
                )
                session.add(msg)
                count += 1

        await session.commit()
    print(f"[OK] 创建 {count} 条消息（含多轮真实对话）")


async def seed_profiles(semester_ids, student_ids, submission_ids):
    """创建学生画像数据（所有字段填充）"""
    async with async_session_factory() as session:
        count = 0
        for s_idx, sid in enumerate(student_ids):
            total_subs = random.randint(1, 4)
            approved = random.randint(0, total_subs)
            sub_id = submission_ids[s_idx] if s_idx < len(submission_ids) else None

            profile = ProfileSnapshot(
                student_id=sid,
                semester_id=semester_ids[1],
                computed_from_submission_id=sub_id,
                radar_json=random_radar_json(),
                trend_json=random_trend_json(random.randint(3, 6)),
                action_items_json=random_action_items(),
                overall_score=round(random.uniform(62, 94), 1),
                total_submissions=total_subs,
                approved_submissions=approved,
            )
            session.add(profile)
            count += 1

            # 为部分学生创建历史画像（模拟成长趋势）
            if s_idx < 10:
                old_profile = ProfileSnapshot(
                    student_id=sid,
                    semester_id=semester_ids[0],  # 上学期
                    radar_json=random_radar_json(),
                    trend_json=random_trend_json(random.randint(2, 4)),
                    action_items_json=random_action_items(),
                    overall_score=round(random.uniform(55, 80), 1),
                    total_submissions=random.randint(3, 6),
                    approved_submissions=random.randint(2, 5),
                )
                session.add(old_profile)
                count += 1

        await session.commit()
    print(f"[OK] 创建 {count} 条画像数据（含radar/trend/action_items/computed_from_submission_id全字段）")


async def seed_practice_sessions(student_ids, submission_ids):
    """创建AI备课练习会话（丰富的对话和报告数据）"""
    sessions_configs = [
        {"title": "《草原》课堂模拟练习", "grade": "五年级", "personality": "active"},
        {"title": "《三角形内角和》教学练习", "grade": "四年级", "personality": "shy"},
        {"title": "《My Family》口语教学练习", "grade": "三年级", "personality": "curious"},
        {"title": "《种子发芽》探究教学练习", "grade": "五年级", "personality": "active"},
        {"title": "《分数的初步认识》概念教学练习", "grade": "三年级", "personality": "shy"},
    ]

    sample_conversations = [
        [
            {"role": "system", "content": "你是一个五年级的虚拟学生，性格活泼好动，对新事物充满好奇。"},
            {"role": "assistant", "content": "老师好！今天我们学什么呀？我昨天在电视上看到了大草原，特别漂亮！"},
            {"role": "user", "content": "同学们好！今天我们来学习老舍先生写的《草原》这篇课文。在学习之前，老师想问大家，你们有没有见过草原？或者在电视、图片上看到过？"},
            {"role": "assistant", "content": "老师我看过！就是那种一望无际的绿色！还有很多羊在上面吃草！特别壮观！"},
            {"role": "user", "content": "说得很好！你的观察力真强。那大家想不想知道，著名作家老舍先生第一次看到草原时是什么感受呢？让我们一起打开课本，走进老舍笔下的草原世界。请大家齐读课文第一自然段。"},
            {"role": "assistant", "content": "（朗读）'这次，我看到了草原。那里的天比别处的更可爱......' 老师，这里说'天底下一碧千里'，一碧千里是什么意思啊？"},
            {"role": "user", "content": "问得好！'一碧千里'是一个成语，意思是一眼望去全是碧绿的颜色，形容草原非常广阔，到处都是绿色。大家想象一下，站在草原上，四面八方看过去都是绿色的草地，是不是特别壮观？"},
            {"role": "assistant", "content": "哇，那得多大啊！老师，老舍爷爷是不是特别喜欢草原？我觉得他写得好美！"},
            {"role": "user", "content": "是的！老舍先生非常热爱草原。现在请大家默读第一段，找出文中描写草原美景的句子，用波浪线画出来，一会儿我们一起分享。给大家3分钟时间。"},
            {"role": "assistant", "content": "老师我找到了好几句！'在天底下，一碧千里，而并不茫茫'还有'四面都有小丘，平地是绿的，小丘也是绿的'，这些都是在写草原的美景对吧？"},
        ],
        [
            {"role": "system", "content": "你是一个四年级的虚拟学生，性格比较害羞，不太主动发言但思维活跃。"},
            {"role": "assistant", "content": "...（安静地坐着看老师）"},
            {"role": "user", "content": "同学们好！上节课我们学习了三角形的分类，今天我们来探究一个很有趣的问题——三角形的内角和到底是多少度？请大家先猜一猜。"},
            {"role": "assistant", "content": "（小声地）...应该是180度吧...我在课外书上好像看到过..."},
            {"role": "user", "content": "这位同学说的对不对呢？我们不能只靠猜测，要用数学的方法来验证。现在请每位同学拿出量角器和三角形纸片，我们来做一个实验。先量出三角形三个角的度数，然后加起来。"},
            {"role": "assistant", "content": "（认真测量后）老师，我量的第一个角是65度，第二个角是72度，第三个角是...43度，加起来是180度！"},
            {"role": "user", "content": "非常好！你测量得很仔细。其他同学的结果是多少呢？有没有不是180度的？"},
            {"role": "assistant", "content": "（举手）老师...我同桌量出来是179度，会不会是测量的时候有一点误差？"},
            {"role": "user", "content": "你说得太好了！测量确实会有一些误差，这是正常的。但我们发现，大家的结果都接近180度。除了测量法，我们还可以用另一种方法来验证——撕拼法。请大家把三角形的三个角撕下来，拼在一起看看。"},
        ],
    ]

    async with async_session_factory() as session:
        count = 0
        for s_idx, sid in enumerate(student_ids[:15]):
            sessions_to_create = random.sample(sessions_configs, k=random.randint(2, min(4, len(sessions_configs))))
            for ps_data in sessions_to_create:
                started = datetime.now() - timedelta(days=random.randint(1, 25), hours=random.randint(0, 12))
                ended = started + timedelta(minutes=random.randint(8, 35))
                conv = random.choice(sample_conversations)
                msg_count = len(conv)
                rating = round(random.uniform(65, 96), 1)

                report = json.dumps({
                    "overall_rating": rating,
                    "response_quality": random.choice(["excellent", "good", "average"]),
                    "overall_comment": random.choice([
                        "整体表现良好，教学语言亲切自然，能有效引导学生思考。课堂节奏把控合理，师生互动频繁。",
                        "教学思路清晰，但语言表达偶有停顿。建议加强对教学内容的熟悉程度，减少对教案的依赖。",
                        "表现优秀！教学设计富有创意，善于激发学生兴趣。提问技巧运用娴熟，能针对学生回答给出有效反馈。",
                    ]),
                    "strengths": random.sample([
                        "教学语言亲切自然", "善于引导提问", "课堂氛围活跃", "板书设计清晰",
                        "教学节奏把控好", "知识讲解准确", "善于使用教具", "耐心回应学生",
                    ], k=random.randint(3, 5)),
                    "weaknesses": random.sample([
                        "互动频率可增加", "评价语言较单一", "时间分配需优化",
                        "过渡语言需打磨", "对学情预估不足",
                    ], k=random.randint(1, 3)),
                    "suggestions": random.sample([
                        "可以增加板书环节", "注意时间分配", "多使用鼓励性语言",
                        "提问后给学生更多思考时间", "增加小组合作学习环节",
                        "注意关注全体学生而非个别学生",
                    ], k=random.randint(2, 4)),
                    "dimensions": {
                        "language_score": round(random.uniform(65, 95), 1),
                        "interaction_score": round(random.uniform(60, 92), 1),
                        "content_score": round(random.uniform(70, 96), 1),
                        "management_score": round(random.uniform(60, 90), 1),
                    },
                    "duration_minutes": round((ended - started).total_seconds() / 60, 1),
                    "total_exchanges": msg_count,
                }, ensure_ascii=False)

                ps = PracticeSession(
                    student_id=sid,
                    submission_id=submission_ids[s_idx] if s_idx < len(submission_ids) else None,
                    title=ps_data["title"],
                    grade=ps_data["grade"],
                    personality=ps_data["personality"],
                    messages_json=json.dumps(conv, ensure_ascii=False),
                    report_json=report,
                    message_count=msg_count,
                    overall_rating=rating,
                    started_at=started,
                    ended_at=ended,
                )
                session.add(ps)
                count += 1

        await session.commit()
    print(f"[OK] 创建 {count} 条练习会话（含完整对话历史/详细报告/submission_id/personality等全字段）")


async def seed_rubrics(semester_ids, instructor_ids):
    """创建评分规则（所有字段）"""
    async with async_session_factory() as session:
        rubric1 = GradingRubric(
            name="标准试讲评分规则（2025春季）",
            description="适用于2025春季学期师范生试讲训练的标准评分规则，包含教案和视频两个维度，共10个评分子维度。评分采用百分制，最终成绩 = 教案分×40% + 视频分×60%。",
            instructor_id=instructor_ids[0],
            semester_id=semester_ids[1],
            is_default=True,
            is_active=True,
            lesson_plan_weight=40.0,
            video_weight=60.0,
            lesson_plan_dimensions=json.dumps([
                {"name": "教学目标", "key": "objectives", "weight": 20, "description": "三维目标是否明确、具体、可操作，是否符合课程标准"},
                {"name": "教学设计", "key": "design", "weight": 30, "description": "教学过程设计是否合理有序，各环节时间分配是否恰当"},
                {"name": "重难点分析", "key": "key_points", "weight": 20, "description": "重难点把握是否准确，突破策略是否有效"},
                {"name": "教学方法", "key": "methods", "weight": 15, "description": "教学方法选择是否恰当，是否体现以学生为中心"},
                {"name": "板书设计", "key": "blackboard", "weight": 15, "description": "板书是否规范美观，是否有助于知识结构呈现"},
            ], ensure_ascii=False),
            video_dimensions=json.dumps([
                {"name": "语言表达", "key": "language", "weight": 25, "description": "语言是否规范、流畅、富有感染力，普通话是否标准"},
                {"name": "教态仪表", "key": "manner", "weight": 15, "description": "教态是否自然大方，衣着是否整洁得体"},
                {"name": "课堂互动", "key": "interaction", "weight": 25, "description": "师生互动是否有效，提问是否有层次"},
                {"name": "教学节奏", "key": "pacing", "weight": 20, "description": "教学节奏是否合理，重点是否突出"},
                {"name": "时间把控", "key": "time", "weight": 15, "description": "是否在规定时间内完成，时间分配是否合理"},
            ], ensure_ascii=False),
            grade_levels=json.dumps([
                {"min": 90, "max": 100, "label": "优秀", "description": "教学能力突出，具备独立执教能力"},
                {"min": 80, "max": 89, "label": "良好", "description": "教学能力较强，基本功扎实"},
                {"min": 70, "max": 79, "label": "中等", "description": "基本达标，部分环节需要改进"},
                {"min": 60, "max": 69, "label": "及格", "description": "尚需加强练习和指导"},
                {"min": 0, "max": 59, "label": "不及格", "description": "需要重新学习和大量练习"},
            ], ensure_ascii=False),
        )

        rubric2 = GradingRubric(
            name="英语试讲专用评分规则",
            description="适用于英语学科试讲的专用评分规则，增加了英语口语流利度和课堂用语规范性维度。",
            instructor_id=instructor_ids[2],
            semester_id=semester_ids[1],
            is_default=False,
            is_active=True,
            lesson_plan_weight=35.0,
            video_weight=65.0,
            lesson_plan_dimensions=json.dumps([
                {"name": "教学目标", "key": "objectives", "weight": 20, "description": "语言技能目标和文化意识目标是否明确"},
                {"name": "活动设计", "key": "activities", "weight": 35, "description": "语言操练活动是否多样，是否包含PPP或TBLT流程"},
                {"name": "分层设计", "key": "differentiation", "weight": 25, "description": "是否考虑不同水平学生的需求"},
                {"name": "资源运用", "key": "resources", "weight": 20, "description": "教学资源是否丰富（图片、音视频、实物等）"},
            ], ensure_ascii=False),
            video_dimensions=json.dumps([
                {"name": "英语口语", "key": "oral_english", "weight": 30, "description": "英语发音是否准确，语调是否自然"},
                {"name": "课堂用语", "key": "classroom_language", "weight": 20, "description": "课堂指令是否清晰，英语使用比例"},
                {"name": "互动效果", "key": "interaction", "weight": 25, "description": "活动组织是否有效，学生参与度"},
                {"name": "教态表现", "key": "manner", "weight": 25, "description": "是否运用TPR，教态是否活泼生动"},
            ], ensure_ascii=False),
            grade_levels=json.dumps([
                {"min": 90, "max": 100, "label": "Excellent", "description": "Outstanding teaching performance"},
                {"min": 80, "max": 89, "label": "Good", "description": "Solid teaching skills"},
                {"min": 70, "max": 79, "label": "Satisfactory", "description": "Meets basic requirements"},
                {"min": 60, "max": 69, "label": "Pass", "description": "Needs improvement"},
                {"min": 0, "max": 59, "label": "Fail", "description": "Requires significant improvement"},
            ], ensure_ascii=False),
        )

        session.add_all([rubric1, rubric2])
        await session.commit()
    print(f"[OK] 创建 2 套评分规则（含全部维度/权重/等级描述）")


async def seed_ai_call_logs(student_ids, instructor_ids, submission_ids):
    """创建AI调用日志（所有字段）"""
    call_types = ["analyze", "video_analyze", "chat", "generate", "summary", "improve"]
    providers_models = [
        ("dashscope", "qwen-plus"),
        ("dashscope", "qwen-turbo"),
        ("dashscope", "qwen-max"),
        ("dashscope", "qwen-audio-turbo"),
        ("dashscope", "qwen-vl-max"),
        ("openai", "gpt-4o-mini"),
        ("deepseek", "deepseek-chat"),
    ]
    ips = ["192.168.1." + str(random.randint(10, 200)) for _ in range(20)]

    async with async_session_factory() as session:
        count = 0
        all_users = student_ids + instructor_ids

        for _ in range(100):
            ct = random.choice(call_types)
            uid = random.choice(all_users)
            provider, model = random.choice(providers_models)
            sub_id = random.choice(submission_ids) if submission_ids and ct in ["analyze", "video_analyze", "improve"] else None
            is_success = random.random() > 0.05
            input_tokens = random.randint(300, 6000)
            output_tokens = random.randint(150, 3000)

            log = AICallLog(
                user_id=uid,
                submission_id=sub_id,
                call_type=ct,
                provider=provider,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                audio_seconds=round(random.uniform(60, 900), 1) if ct == "video_analyze" else 0.0,
                latency_ms=random.randint(500, 20000),
                is_success=is_success,
                error_message="API rate limit exceeded, please retry after 60s" if not is_success else None,
                request_summary=f"{ct} - user#{uid}" + (f" - submission#{sub_id}" if sub_id else ""),
                ip_address=random.choice(ips),
            )
            session.add(log)
            count += 1

        await session.commit()
    print(f"[OK] 创建 {count} 条AI调用日志（含ip_address/error_message/audio_seconds等全字段）")


# ==================== 主入口 ====================

async def main():
    print("=" * 60)
    print("  全量测试数据生成（增强版）")
    print("=" * 60)
    print()

    # 0. 确保所有表存在
    await ensure_tables()

    # 1. 清除旧数据
    await clear_old_data()

    # 2. 用户
    instructor_ids, student_ids = await seed_users()

    # 3. 批次
    semester_ids = await seed_semesters()

    # 4. 分组
    await seed_groups(semester_ids, instructor_ids, student_ids)

    # 5. 任务
    task_ids = await seed_tasks(semester_ids, instructor_ids)

    # 6. 提交
    submission_ids = await seed_submissions(task_ids, student_ids, instructor_ids)

    # 7. 公告
    await seed_notices(semester_ids)

    # 8. 通知
    try:
        await seed_notifications(student_ids, instructor_ids)
    except Exception as e:
        print(f"[SKIP] 通知: {e}")

    # 9. 消息
    await seed_messages(semester_ids, student_ids, instructor_ids)

    # 10. 画像
    await seed_profiles(semester_ids, student_ids, submission_ids)

    # 11. 练习会话
    await seed_practice_sessions(student_ids, submission_ids)

    # 12. 评分规则
    await seed_rubrics(semester_ids, instructor_ids)

    # 13. AI调用日志
    await seed_ai_call_logs(student_ids, instructor_ids, submission_ids)

    print()
    print("=" * 60)
    print("  数据生成完毕！")
    print("=" * 60)
    print()
    print("测试账号：")
    print("  管理员: admin / admin123")
    print(f"  教 师: T001~T00{len(INSTRUCTORS)} (密码 = 账号)")
    print(f"  学 生: S2021001~S20210{len(STUDENTS):02d} (密码 = 账号)")
    print()
    print("数据概览：")
    print(f"  教师: {len(INSTRUCTORS)} 人 (含email/phone/college/major/remark)")
    print(f"  学生: {len(STUDENTS)} 人 (含email/phone/college/major/class_name/head_teacher)")
    print(f"  批次: 3 个 (已完成+进行中+筹备中)")
    print(f"  任务: {len(TASKS_DATA)} 个 (含过期/进行中/未开始，含attachment)")
    print(f"  提交: {len(submission_ids)} 条 (approved/rejected/graded/pending全状态)")
    print(f"  公告: {len(NOTICE_DATA)} 条 (dialog/marquee/both全类型)")
    print(f"  画像: {len(student_ids) + min(10, len(student_ids))} 条 (含跨学期历史)")
    print(f"  AI日志: 100 条")
    print()


if __name__ == "__main__":
    asyncio.run(main())

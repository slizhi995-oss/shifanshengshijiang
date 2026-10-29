# -*- coding: utf-8 -*-
"""生成计划书所需的所有图表图片"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import os

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'KaiTi']
plt.rcParams['axes.unicode_minus'] = False
plt.rcParams['figure.dpi'] = 200

OUT_DIR = os.path.join(os.path.dirname(__file__), 'plan_images')
os.makedirs(OUT_DIR, exist_ok=True)

# ========== 图3-1 师范生在校人数增长趋势 ==========
def chart_3_1():
    years = ['2018', '2019', '2020', '2021', '2022', '2023', '2024']
    vals = [180, 200, 220, 240, 260, 280, 300]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    bars = ax.bar(years, vals, color='#4472C4', width=0.55, edgecolor='white')
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width()/2, v + 4, f'{v}', ha='center', va='bottom', fontsize=10, fontweight='bold')
    ax.set_ylabel('在校人数（万人）', fontsize=12)
    ax.set_xlabel('年份', fontsize=12)
    ax.set_title('图3-1  我国师范生在校人数增长趋势', fontsize=13, fontweight='bold')
    ax.set_ylim(0, 340)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, 'chart_3_1.png'))
    plt.close(fig)

# ========== 图3-2 导师工作量构成饼图 ==========
def chart_3_2():
    labels = ['批改教案\n(5小时)', '观看视频\n(6小时)', '撰写反馈\n(3小时)', '沟通答疑\n(1小时)']
    sizes = [5, 6, 3, 1]
    colors = ['#4472C4', '#ED7D31', '#A5A5A5', '#FFC000']
    fig, ax = plt.subplots(figsize=(6, 6))
    wedges, texts, autotexts = ax.pie(sizes, labels=labels, colors=colors, autopct='%1.0f%%',
                                       startangle=90, textprops={'fontsize': 11})
    for at in autotexts:
        at.set_fontweight('bold')
    ax.set_title('图3-2  一位导师每轮工作量构成（30名学生）', fontsize=13, fontweight='bold', pad=15)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, 'chart_3_2.png'))
    plt.close(fig)

# ========== 图3-3 传统评价 vs 本系统评价 流程对比 ==========
def chart_3_3():
    fig, axes = plt.subplots(2, 1, figsize=(10, 5.5))
    # 传统
    ax = axes[0]
    ax.set_xlim(0, 10); ax.set_ylim(0, 1)
    ax.axis('off')
    ax.set_title('传统评价方式', fontsize=12, fontweight='bold', loc='left', color='#C00000')
    steps_t = ['学生提交', '教师人工批改', '总分+简短评语', '仅记录最终成绩']
    xs = [1, 3.3, 5.8, 8.3]
    for i, (x, s) in enumerate(zip(xs, steps_t)):
        color = '#D9E2F3' if i < 3 else '#F2DCDB'
        ax.add_patch(plt.Rectangle((x-0.7, 0.2), 1.8, 0.6, facecolor=color, edgecolor='#333', linewidth=1.2, zorder=2))
        ax.text(x+0.2, 0.5, s, ha='center', va='center', fontsize=9, zorder=3)
        if i < len(steps_t)-1:
            ax.annotate('', xy=(xs[i+1]-0.7, 0.5), xytext=(x+1.1, 0.5),
                        arrowprops=dict(arrowstyle='->', color='#666', lw=1.5))
    # 本系统
    ax2 = axes[1]
    ax2.set_xlim(0, 12); ax2.set_ylim(0, 1)
    ax2.axis('off')
    ax2.set_title('本系统评价方式', fontsize=12, fontweight='bold', loc='left', color='#0070C0')
    steps_n = ['学生提交', 'AI自动分析\n7+10维度', '教师AI辅助\n批改', '结构化评分\n+改进建议', '画像快照\n存储', '雷达图+\n趋势图']
    xs2 = [0.8, 2.7, 4.8, 6.9, 9.0, 11.0]
    for i, (x, s) in enumerate(zip(xs2, steps_n)):
        color = '#DAEEF3' if i not in [1, 5] else '#E2EFDA'
        ax2.add_patch(plt.Rectangle((x-0.7, 0.15), 1.6, 0.7, facecolor=color, edgecolor='#333', linewidth=1.2, zorder=2))
        ax2.text(x+0.1, 0.5, s, ha='center', va='center', fontsize=8, zorder=3)
        if i < len(steps_n)-1:
            ax2.annotate('', xy=(xs2[i+1]-0.7, 0.5), xytext=(x+0.9, 0.5),
                        arrowprops=dict(arrowstyle='->', color='#0070C0', lw=1.5))
    fig.suptitle('图3-3  传统评价方式与本系统评价方式对比', fontsize=13, fontweight='bold', y=1.02)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, 'chart_3_3.png'), bbox_inches='tight')
    plt.close(fig)

# ========== 图3-4 教师端调研数据 ==========
def chart_3_4():
    labels = ['对批改效率满意', '认为标准需统一', '希望AI辅助']
    vals = [23, 87, 92]
    colors = ['#ED7D31', '#4472C4', '#4472C4']
    fig, ax = plt.subplots(figsize=(7, 4))
    bars = ax.barh(labels, vals, color=colors, height=0.5, edgecolor='white')
    for b, v in zip(bars, vals):
        ax.text(v + 1.5, b.get_y() + b.get_height()/2, f'{v}%', va='center', fontsize=11, fontweight='bold')
    ax.set_xlim(0, 105)
    ax.set_xlabel('百分比（%）', fontsize=11)
    ax.set_title('图3-4  教师端调研结果', fontsize=13, fontweight='bold')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, 'chart_3_4.png'))
    plt.close(fig)

# ========== 图3-5 学生端调研数据 ==========
def chart_3_5():
    labels = ['反馈不够具体', '希望量化指标', '缺乏互动练习', '希望追踪成长']
    vals = [76, 89, 94, 91]
    fig, ax = plt.subplots(figsize=(7, 4.5))
    bars = ax.barh(labels, vals, color='#4472C4', height=0.5, edgecolor='white')
    for b, v in zip(bars, vals):
        ax.text(v + 1.5, b.get_y() + b.get_height()/2, f'{v}%', va='center', fontsize=11, fontweight='bold')
    ax.set_xlim(0, 105)
    ax.set_xlabel('百分比（%）', fontsize=11)
    ax.set_title('图3-5  学生端调研结果', fontsize=13, fontweight='bold')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, 'chart_3_5.png'))
    plt.close(fig)

# ========== 图3-6 竞品雷达图 ==========
def chart_3_6():
    cats = ['教案分析', '视频评估', '备课互动', '教务管理', '成长画像', 'AI批改', '运营治理', '私有化部署']
    N = len(cats)
    angles = np.linspace(0, 2*np.pi, N, endpoint=False).tolist()
    angles += angles[:1]
    def add_curve(ax, vals, label, color, ls='-'):
        v = vals + vals[:1]
        ax.plot(angles, v, color=color, linewidth=2, linestyle=ls, label=label)
        ax.fill(angles, v, color=color, alpha=0.1)

    fig, ax = plt.subplots(figsize=(7, 7), subplot_kw=dict(polar=True))
    ax.set_theta_offset(np.pi/2)
    ax.set_theta_direction(-1)
    ax.set_thetagrids(np.degrees(angles[:-1]), cats, fontsize=10)
    ax.set_ylim(0, 100)
    ax.set_yticks([20, 40, 60, 80, 100])
    ax.set_yticklabels(['20', '40', '60', '80', '100'], fontsize=8, color='grey')

    add_curve(ax, [95,90,95,90,95,92,85,95], '智教领航（本系统）', '#4472C4')
    add_curve(ax, [5,5,5,80,5,5,5,5], '传统教务系统', '#ED7D31', '--')
    add_curve(ax, [40,5,30,5,5,20,5,5], '通用AI工具', '#A5A5A5', '-.')
    add_curve(ax, [5,40,5,5,5,5,5,5], '语音分析产品', '#FFC000', ':')
    ax.legend(loc='upper right', bbox_to_anchor=(1.35, 1.1), fontsize=9)
    ax.set_title('图3-6  竞品能力覆盖对比', fontsize=13, fontweight='bold', pad=20)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, 'chart_3_6.png'), bbox_inches='tight')
    plt.close(fig)

# ========== 图4-1 系统功能结构图 ==========
def chart_4_1():
    fig, ax = plt.subplots(figsize=(12, 7))
    ax.axis('off')
    ax.set_xlim(0, 12); ax.set_ylim(0, 7)

    def box(x, y, w, h, text, color, fs=9):
        ax.add_patch(plt.Rectangle((x, y), w, h, facecolor=color, edgecolor='#333', linewidth=1, zorder=2))
        ax.text(x+w/2, y+h/2, text, ha='center', va='center', fontsize=fs, zorder=3, fontweight='bold' if fs>9 else 'normal')

    # 顶层
    box(4.5, 6.0, 3, 0.7, '智教领航系统', '#4472C4', 12)
    # 五大模块
    mods = ['教案智能\n处理', '视频多模态\n分析', 'AI辅助\n教学', '教务\n管理', '成长\n画像']
    colors_m = ['#D6E4F0', '#FCE4D6', '#E2EFDA', '#D9E2F3', '#EDEDED']
    xs_m = [0.3, 2.6, 4.9, 7.2, 9.5]
    for i, (x, m, c) in enumerate(zip(xs_m, mods, colors_m)):
        box(x, 4.2, 2.0, 0.9, m, c, 9)
        ax.annotate('', xy=(x+1.0, 5.1), xytext=(6.0, 6.0),
                    arrowprops=dict(arrowstyle='->', color='#666', lw=1))
    # 子功能
    sub = [
        ['七维度分析', '教案摘要', '改进建议', '评语生成', '教案生成'],
        ['语速/停顿', '语气词/ASR', '姿态/手势', '眼神/表情', '空间运用'],
        ['备课助手', '角色扮演', '练习报告', 'AI批改', '五项一键AI'],
        ['用户管理', '批次/分组', '任务/提交', '批改/成绩', '公告/消息'],
        ['能力雷达图', '趋势折线图', '行动建议', '', ''],
    ]
    for i, (x, subs) in enumerate(zip(xs_m, sub)):
        for j, s in enumerate(subs):
            if not s:
                continue
            yy = 3.3 - j*0.55
            box(x, yy, 2.0, 0.45, s, '#F2F2F2', 7)
            if j == 0:
                ax.annotate('', xy=(x+1.0, 3.75), xytext=(x+1.0, 4.2),
                            arrowprops=dict(arrowstyle='->', color='#999', lw=0.8))

    ax.set_title('图4-1  系统功能结构图', fontsize=14, fontweight='bold', pad=10)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, 'chart_4_1.png'), bbox_inches='tight')
    plt.close(fig)

# ========== 图4-2 系统技术架构图 ==========
def chart_4_2():
    fig, ax = plt.subplots(figsize=(10, 8))
    ax.axis('off')
    ax.set_xlim(0, 10); ax.set_ylim(0, 8)

    def layer(y, h, text, color, sub_texts=None):
        ax.add_patch(plt.Rectangle((0.5, y), 9, h, facecolor=color, edgecolor='#333', linewidth=1.2, zorder=2))
        ax.text(5, y+h-0.25, text, ha='center', va='center', fontsize=11, fontweight='bold', zorder=3)
        if sub_texts:
            total = len(sub_texts)
            w = 8.4 / total
            for i, st in enumerate(sub_texts):
                sx = 0.8 + i*w
                ax.add_patch(plt.Rectangle((sx, y+0.15), w-0.2, 0.5, facecolor='white', edgecolor='#999',
                                           linewidth=0.8, zorder=3, alpha=0.8))
                ax.text(sx+(w-0.2)/2, y+0.4, st, ha='center', va='center', fontsize=8, zorder=4)

    layer(7.0, 0.8, '客户端层：Vue3 + TypeScript + Vite + ElementPlus + ECharts', '#D6E4F0')
    layer(5.9, 0.8, '网关层：Nginx 反向代理 + HTTPS + CORS', '#EDEDED')
    layer(4.4, 1.2, '服务层：FastAPI + AsyncSQLAlchemy + JWT鉴权', '#E2EFDA',
          ['教务服务', 'AI服务层', '画像服务'])
    layer(2.9, 1.2, 'AI能力层：三模型协同', '#FCE4D6',
          ['qwen-plus\n文本模型', 'qwen-omni-turbo\n音频模型', 'qwen-vl-max\n视觉模型'])
    layer(1.8, 0.8, '数据层：MySQL 8.0 + 文件存储 /uploads', '#D9E2F3')
    layer(0.7, 0.8, '部署层：Docker + Docker Compose + Linux服务器', '#F2DCDB')

    for y in [7.0, 5.9, 5.6, 4.1, 3.6, 2.6]:
        ax.annotate('', xy=(5, y), xytext=(5, y+0.2),
                    arrowprops=dict(arrowstyle='->', color='#666', lw=1))

    ax.set_title('图4-2  系统技术架构图', fontsize=14, fontweight='bold', pad=10)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, 'chart_4_2.png'), bbox_inches='tight')
    plt.close(fig)

# ========== 图4-3 使用流程图 ==========
def chart_4_3():
    fig, ax = plt.subplots(figsize=(11, 8))
    ax.axis('off')
    ax.set_xlim(0, 11); ax.set_ylim(0, 8)

    def rbox(x, y, w, h, text, color, fs=8):
        ax.add_patch(mpatches.FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.1",
                     facecolor=color, edgecolor='#333', linewidth=1, zorder=2))
        ax.text(x+w/2, y+h/2, text, ha='center', va='center', fontsize=fs, zorder=3)

    def arrow(x1, y1, x2, y2, text=''):
        ax.annotate(text, xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle='->', color='#4472C4', lw=1.5),
                    fontsize=7, ha='center', va='center', color='#666')

    # 管理员流程
    rbox(0.3, 7.0, 2.0, 0.6, '管理员创建批次', '#D6E4F0', 9)
    rbox(3.0, 7.0, 2.2, 0.6, 'Excel批量导入\n学生/教师', '#D6E4F0', 8)
    rbox(6.0, 7.0, 2.2, 0.6, '一键自动\n均衡分组', '#D6E4F0', 8)
    arrow(2.3, 7.3, 3.0, 7.3)
    arrow(5.2, 7.3, 6.0, 7.3)

    # 教师
    rbox(0.3, 5.5, 2.5, 0.6, '教师创建并发布任务', '#E2EFDA', 9)
    arrow(7.1, 7.0, 1.5, 6.1)

    # 学生提交
    rbox(4.0, 5.5, 2.2, 0.6, '学生上传\n教案+视频', '#FFF2CC', 9)
    arrow(2.8, 5.8, 4.0, 5.8)

    # AI分析
    rbox(3.0, 4.0, 2.5, 0.7, '系统自动触发\nAI分析', '#FCE4D6', 9)
    arrow(5.1, 5.5, 4.25, 4.7)

    # 分支
    rbox(0.3, 3.0, 2.2, 0.6, '教案七维度分析', '#D6E4F0', 8)
    rbox(0.3, 2.1, 2.2, 0.6, '视频多模态分析', '#D6E4F0', 8)
    arrow(3.0, 4.0, 1.4, 3.6)
    arrow(3.0, 4.0, 1.4, 2.7)

    # 学生查看
    rbox(6.5, 3.0, 2.2, 0.6, '学生查看\nAI分析报告', '#E2EFDA', 8)
    rbox(6.5, 2.1, 2.2, 0.6, '学生使用\nAI备课助手', '#E2EFDA', 8)
    arrow(2.5, 3.3, 6.5, 3.3)
    arrow(2.5, 2.4, 6.5, 2.4)

    # 教师批改
    rbox(3.5, 1.0, 2.5, 0.7, '教师AI辅助批改\n（五项一键AI）', '#FCE4D6', 8)
    arrow(1.4, 2.1, 4.75, 1.7)

    # 评分
    rbox(7.0, 1.0, 2.0, 0.7, '审核修改后\n提交评分', '#D6E4F0', 8)
    arrow(6.0, 1.35, 7.0, 1.35)

    # 成长画像
    rbox(3.5, -0.1, 3.0, 0.7, '成长画像\n雷达图+趋势图+建议', '#DAEEF3', 9)
    arrow(8.0, 1.0, 5.0, 0.6)
    arrow(7.6, 2.1, 5.0, 0.6)

    ax.set_title('图4-3  系统使用全流程图', fontsize=14, fontweight='bold', pad=10)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, 'chart_4_3.png'), bbox_inches='tight')
    plt.close(fig)

# ========== 图5-1 商业模式三方关系图 ==========
def chart_5_1():
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.axis('off')
    ax.set_xlim(0, 11); ax.set_ylim(0, 5)

    def rbox(x, y, w, h, text, color, fs=9):
        ax.add_patch(mpatches.FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.15",
                     facecolor=color, edgecolor='#333', linewidth=1.2, zorder=2))
        ax.text(x+w/2, y+h/2, text, ha='center', va='center', fontsize=fs, zorder=3)

    # 需求端
    rbox(0.2, 3.5, 2.5, 1.0, '高校师范学院\n教务管理人员', '#D6E4F0', 9)
    rbox(0.2, 1.8, 2.5, 1.0, '指导教师\n（约5万人）', '#D6E4F0', 9)
    rbox(0.2, 0.2, 2.5, 1.0, '师范生\n（约300万人）', '#D6E4F0', 9)

    # 平台
    rbox(3.8, 3.2, 3.0, 1.2, 'AI智能分析引擎\n教案+视频+备课', '#FFF2CC', 10)
    rbox(3.8, 1.6, 3.0, 1.0, '教务管理系统\n批次/分组/任务/成绩', '#E2EFDA', 9)
    rbox(3.8, 0.2, 3.0, 1.0, '成长画像系统\n雷达图+趋势图+建议', '#DAEEF3', 9)

    ax.text(5.3, 4.7, '智教领航平台', ha='center', fontsize=13, fontweight='bold', color='#4472C4')

    # 能力供给端
    rbox(8.0, 3.2, 2.5, 0.8, 'qwen-plus\n文本模型', '#FCE4D6', 9)
    rbox(8.0, 2.0, 2.5, 0.8, 'qwen-omni-turbo\n音频模型', '#FCE4D6', 9)
    rbox(8.0, 0.8, 2.5, 0.8, 'qwen-vl-max\n视觉模型', '#FCE4D6', 9)

    # 箭头
    for y in [4.0, 2.3, 0.7]:
        ax.annotate('', xy=(3.8, y), xytext=(2.7, y),
                    arrowprops=dict(arrowstyle='->', color='#4472C4', lw=1.5))
    for y in [3.6, 2.4, 1.2]:
        ax.annotate('', xy=(8.0, y), xytext=(6.8, y),
                    arrowprops=dict(arrowstyle='->', color='#ED7D31', lw=1.5))

    ax.text(3.2, 4.3, 'SaaS订阅/\n私有化部署', ha='center', fontsize=7, color='#4472C4')
    ax.text(7.5, 4.0, 'API调用', ha='center', fontsize=7, color='#ED7D31')

    ax.set_title('图5-1  商业模式三方关系示意图', fontsize=14, fontweight='bold', pad=10)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, 'chart_5_1.png'), bbox_inches='tight')
    plt.close(fig)

# ========== 图7-1 五年收入与净利润趋势 ==========
def chart_7_1():
    years = ['T+1年', 'T+2年', 'T+3年', 'T+4年', 'T+5年']
    revenue = [15, 45, 90, 150, 220]
    profit = [0.4, 11.6, 30.8, 57.8, 90.5]
    x = np.arange(len(years))
    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(x, revenue, width=0.5, color='#4472C4', alpha=0.7, label='主营业务收入')
    ax.plot(x, profit, color='#ED7D31', marker='o', linewidth=2.5, markersize=8, label='净利润', zorder=5)
    for i, (r, p) in enumerate(zip(revenue, profit)):
        ax.text(i, r+5, f'{r}', ha='center', fontsize=9, color='#4472C4', fontweight='bold')
        ax.text(i+0.15, p+5, f'{p}', ha='center', fontsize=9, color='#ED7D31', fontweight='bold')
    ax.set_xticks(x); ax.set_xticklabels(years, fontsize=10)
    ax.set_ylabel('金额（万元）', fontsize=11)
    ax.set_title('图7-1  五年收入与净利润增长趋势', fontsize=13, fontweight='bold')
    ax.legend(fontsize=10)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, 'chart_7_1.png'))
    plt.close(fig)

# ========== 图7-2 三类收入趋势 ==========
def chart_7_2():
    years = ['T+1年', 'T+2年', 'T+3年', 'T+4年', 'T+5年']
    saas = [10, 30, 60, 100, 150]
    deploy = [5, 10, 20, 30, 40]
    api = [0, 5, 10, 20, 30]
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(years, saas, marker='s', linewidth=2.5, markersize=8, color='#4472C4', label='SaaS订阅收入')
    ax.plot(years, deploy, marker='^', linewidth=2.5, markersize=8, color='#ED7D31', label='私有化部署收入')
    ax.plot(years, api, marker='o', linewidth=2.5, markersize=8, color='#A5A5A5', label='AI API开放收入')
    ax.set_ylabel('金额（万元）', fontsize=11)
    ax.set_title('图7-2  三类收入来源五年增长趋势', fontsize=13, fontweight='bold')
    ax.legend(fontsize=10)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, 'chart_7_2.png'))
    plt.close(fig)

# ========== 图7-3 资金使用饼图 ==========
def chart_7_3():
    labels = ['AI模型API调用\n2.0万', '服务器租赁\n1.5万', '营销推广\n1.5万',
              '流动资金\n2.0万', '软著费用\n0.5万', '竞赛差旅\n0.5万']
    sizes = [25, 18.75, 18.75, 25, 6.25, 6.25]
    colors = ['#4472C4', '#ED7D31', '#A5A5A5', '#FFC000', '#5B9BD5', '#70AD47']
    fig, ax = plt.subplots(figsize=(7, 7))
    wedges, texts, autotexts = ax.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%',
                                       startangle=90, textprops={'fontsize': 9})
    for at in autotexts:
        at.set_fontsize(9)
        at.set_fontweight('bold')
    ax.set_title('图7-3  初期投资8万元资金使用分配', fontsize=13, fontweight='bold', pad=15)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, 'chart_7_3.png'))
    plt.close(fig)

# ========== 图2-1 组织架构图 ==========
def chart_2_1():
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.axis('off')
    ax.set_xlim(0, 9); ax.set_ylim(0, 5)

    def rbox(x, y, w, h, text, color, fs=9):
        ax.add_patch(mpatches.FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.1",
                     facecolor=color, edgecolor='#333', linewidth=1, zorder=2))
        ax.text(x+w/2, y+h/2, text, ha='center', va='center', fontsize=fs, zorder=3)

    # 顶层
    rbox(3.2, 4.0, 2.5, 0.6, '项目负责人', '#4472C4', 11)
    # 指导教师
    rbox(6.8, 4.0, 1.8, 0.6, '指导教师', '#EDEDED', 9)
    ax.plot([5.7, 6.8], [4.3, 4.3], '--', color='#999', linewidth=1)
    # 三组
    groups = [('技术组', '#D6E4F0'), ('产品组', '#E2EFDA'), ('运营组', '#FCE4D6')]
    gx = [0.8, 3.2, 5.7]
    for x, (name, color) in zip(gx, groups):
        rbox(x, 2.7, 2.2, 0.6, name, color, 10)
        ax.annotate('', xy=(x+1.1, 3.3), xytext=(4.45, 4.0),
                    arrowprops=dict(arrowstyle='->', color='#666', lw=1.2))
    # 子项
    tech = ['后端开发', 'AI集成', '前端开发', '系统运维']
    prod = ['需求调研', '产品设计', '测试验收', '文档编写']
    ops = ['市场推广', '用户支持', '竞赛材料']
    for i, t in enumerate(tech):
        rbox(0.2, 1.8-i*0.5, 1.4, 0.4, t, '#F2F2F2', 8)
        if i == 0:
            ax.plot([1.9, 1.9], [2.7, 2.2], '-', color='#999', linewidth=0.8)
    for i, t in enumerate(prod):
        rbox(3.0, 1.8-i*0.5, 1.4, 0.4, t, '#F2F2F2', 8)
        if i == 0:
            ax.plot([4.3, 4.3], [2.7, 2.2], '-', color='#999', linewidth=0.8)
    for i, t in enumerate(ops):
        rbox(5.8, 1.8-i*0.5, 1.4, 0.4, t, '#F2F2F2', 8)
        if i == 0:
            ax.plot([6.8, 6.8], [2.7, 2.2], '-', color='#999', linewidth=0.8)

    ax.set_title('图2-1  团队组织架构图', fontsize=13, fontweight='bold', pad=10)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, 'chart_2_1.png'), bbox_inches='tight')
    plt.close(fig)

if __name__ == '__main__':
    print('正在生成图表...')
    chart_2_1(); print('  图2-1 组织架构图 ✓')
    chart_3_1(); print('  图3-1 师范生增长趋势 ✓')
    chart_3_2(); print('  图3-2 导师工作量构成 ✓')
    chart_3_3(); print('  图3-3 评价方式对比 ✓')
    chart_3_4(); print('  图3-4 教师端调研 ✓')
    chart_3_5(); print('  图3-5 学生端调研 ✓')
    chart_3_6(); print('  图3-6 竞品雷达图 ✓')
    chart_4_1(); print('  图4-1 功能结构图 ✓')
    chart_4_2(); print('  图4-2 技术架构图 ✓')
    chart_4_3(); print('  图4-3 使用流程图 ✓')
    chart_5_1(); print('  图5-1 商业模式图 ✓')
    chart_7_1(); print('  图7-1 收入利润趋势 ✓')
    chart_7_2(); print('  图7-2 收入结构趋势 ✓')
    chart_7_3(); print('  图7-3 资金分配饼图 ✓')
    print(f'\n所有图表已保存到: {OUT_DIR}')

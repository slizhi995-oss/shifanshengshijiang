"""Directory transcriptions visually checked against these exact scanned PDFs.

Numbers below are PRINTED pages, never PDF positions. The outline parser
still requires corroborating body headings and detects the PDF offset.
"""
REVIEWS = {
    '初中物理九年级上册.pdf': ('245d3ce35bd36a5541f1dd96dd48913fe0c47e1ef8d7a0d676d13436edea02f8', [6, 7], '''
第十一章 物态变化|1
第一节 温度及其测量|2
第二节 熔化与凝固|7
第三节 汽化与液化|12
第四节 升华与凝华|19
第五节 水循环与水资源|21
第十二章 内能与热机|28
第一节 分子动理论|29
第二节 内能|34
第三节 比热容|38
第四节 热机|43
第五节 能量的转化与守恒|49
跨学科实践 调查当地燃料结构及空气质量|53
第十三章 简单电路|59
第一节 电荷|60
第二节 电路 电路图|65
第三节 串联电路与并联电路|71
第十四章 电流 电压 电阻|81
第一节 电流|82
第二节 串、并联电路中电流的规律|87
第三节 电压|91
第四节 串、并联电路中电压的规律|95
第五节 电阻|99
第六节 变阻器|105
跨学科实践 制作水果电池|110
第十五章 欧姆定律|116
第一节 电流与电压、电阻的关系|117
第二节 欧姆定律|121
第三节 电阻的测量|124
第四节 电阻的串联与并联|127
跨学科实践 制作调光台灯|132
'''),
    '初中物理九年级下册.pdf': ('5bb6be162a54047311cb7378a95a9bcd6d7ef7cd9a0eec3c32564d94dfb9d62c', [6, 7], '''
第十六章 电功 电功率|1
第一节 电能与电功|2
第二节 电功率|7
第三节 焦耳定律|12
第十七章 生活用电|22
第一节 家庭电路|23
第二节 安全用电|29
跨学科实践 设计与安装模拟家庭电路|35
第十八章 电与磁|41
第一节 磁现象 磁场|42
第二节 电生磁|48
第三节 电磁铁|53
第四节 电动机|58
第五节 磁生电|63
第十九章 电磁波与通信|72
第一节 模拟通信与数字通信|73
第二节 电磁波|76
第三节 广播、电视与移动通信|81
第四节 现代通信|85
第二十章 能源与环境|93
第一节 能源|94
第二节 核能|99
第三节 太阳能|104
跨学科实践 设计与制作节能小屋模型|108
'''),
    '初中物理八年级下册.pdf': ('388913a8a37a4793d302f79e4ccba5e4f782c14f8198243aaa0a4949d505d28e', [3, 4], '''
第六章 质量和密度|1
第一节 物体的质量及其测量|2
第二节 物质的密度|8
第三节 密度的测量与应用|13
第四节 探索新材料|18
整理与复习|23
第七章 运动和力|24
第一节 力|25
第二节 力的测量 弹力|29
第三节 重力|36
第四节 同一直线上二力的合成|41
第五节 二力平衡|45
第六节 摩擦力|49
第七节 牛顿第一定律|54
整理与复习|59
第八章 压强和浮力|60
第一节 压强|61
第二节 液体压强|67
第三节 探寻连通器|73
第四节 大气压强|79
第五节 流体压强与流速的关系|86
第六节 浮力|91
第七节 物体的浮沉条件及其应用|97
整理与复习|101
第九章 机械和功|102
第一节 杠杆|103
第二节 滑轮|110
第三节 功|115
第四节 比较做功的快慢|120
第五节 探究使用机械是否省功|125
第六节 制作简易升降机|131
整理与复习|138
附录 本册书中首次用到的物理量及其单位|139
'''),
    '高中英语必修一.pdf': ('fe798cdc7010b208a1fa952f3eb4c60d853e50e745908b27e7dc89ad01b7d906', [3, 4], '''
Welcome Unit|1
Unit 1 Teenage Life|11
Unit 2 Travelling Around|23
Unit 3 Sports and Fitness|35
Unit 4 Natural Disasters|47
Unit 5 Languages Around the World|59
Workbook Unit 1|71
'''),
    '高中英语必修二.pdf': ('5efa368d9a61ca18d38bc94fd21784e2c62e4fe40c3711d6d5cc632ab2aa27e9', [3, 4], '''
Unit 1 Cultural Heritage|1
Unit 2 Wildlife Protection|13
Unit 3 The Internet|25
Unit 4 History and Traditions|37
Unit 5 Music|49
Workbook Unit 1|61
'''),
    '高中英语必修三.pdf': ('bbf54118634c423f56edf56cf82e4f6108afc1d941ff80d3112935e85b0ee88a', [3, 4], '''
Unit 1 Festivals and Celebrations|1
Unit 2 Morals and Virtues|13
Unit 3 Diverse Cultures|25
Unit 4 Space Exploration|37
Unit 5 The Value of Money|49
Workbook Unit 1|61
'''),
    '高中英语选择性必修二.pdf': ('31a55f42e3b0fbfaaa9833174ef29dad819428d00b580a88638f96c2882dd10e', [3, 4], '''
Unit 1 Science and Scientists|1
Unit 2 Bridging Cultures|13
Unit 3 Food and Culture|25
Unit 4 Journey Across a Vast Land|37
Unit 5 First Aid|49
Workbook Unit 1|61
'''),
}

# Verified against the first unit/lesson pages and their printed page footers.
PDF_OFFSETS = {'初中物理九年级上册.pdf': 7, '初中物理九年级下册.pdf': 7,
    '初中物理八年级下册.pdf': 4, '高中英语必修一.pdf': 5, '高中英语必修二.pdf': 4,
    '高中英语必修三.pdf': 5, '高中英语选择性必修二.pdf': 4}


def reviewed_contents(book):
    review = REVIEWS.get(book['filename'])
    if not review:
        return None, None
    digest, pages, transcription = review
    if digest != book['sha256']:
        raise ValueError('Reviewed directory belongs to a different PDF')
    entries = []
    for line in transcription.strip().splitlines():
        title, printed = line.rsplit('|', 1)
        entries.append(dict(title=title, printed=int(printed)))
    return entries, pages

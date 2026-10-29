"""
测试视频分析功能
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.video_analysis_service import get_video_analysis_service


async def test_video_analysis():
    """测试视频分析功能"""
    
    print("=" * 60)
    print("视频分析功能测试")
    print("=" * 60)
    
    # 检查是否提供了视频文件路径
    if len(sys.argv) < 2:
        print("\n❌ 请提供视频文件路径")
        print("\n使用方法:")
        print("  python scripts/test_video_analysis.py <video_path>")
        print("\n示例:")
        print("  python scripts/test_video_analysis.py uploads/videos/test.mp4")
        return
    
    video_path = sys.argv[1]
    
    # 检查文件是否存在
    if not Path(video_path).exists():
        print(f"\n❌ 视频文件不存在: {video_path}")
        return
    
    print(f"\n📹 视频文件: {video_path}")
    print("\n开始分析...\n")
    
    try:
        service = get_video_analysis_service()
        
        # 执行分析
        result = await service.analyze_video(video_path)
        
        # 显示结果
        print("=" * 60)
        print("分析结果")
        print("=" * 60)
        
        print(f"\n⏱️  视频时长: {result['duration']:.1f} 秒")
        print(f"📝 文字稿字数: {len(result['transcript'])} 字")
        print(f"🗣️  语速: {result['speech_rate']:.1f} 字/分钟")
        print(f"⏸️  停顿次数: {result['pause_count']} 次")
        print(f"😅 语气词: {result['filler_word_count']} 次")
        
        if result['filler_words']:
            print("\n语气词详情:")
            for word, count in result['filler_words'].items():
                print(f"  - {word}: {count} 次")
        
        print(f"\n⭐ 综合得分: {result['overall_score']:.1f} 分")
        
        print("\n💡 改进建议:")
        for i, suggestion in enumerate(result['suggestions'], 1):
            print(f"  {i}. {suggestion}")
        
        if result.get('gesture_analysis') and 'error' not in result['gesture_analysis']:
            print("\n🤸 动作分析:")
            ga = result['gesture_analysis']
            print(f"  - 姿态得分: {ga['posture_score']:.1f}")
            print(f"  - 手势得分: {ga['gesture_score']:.1f}")
            print(f"  - 综合得分: {ga['overall_gesture_score']:.1f}")
        
        print("\n📄 文字稿预览（前200字）:")
        print(f"  {result['transcript'][:200]}...")
        
        print("\n" + "=" * 60)
        print("✅ 分析完成！")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ 分析失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_video_analysis())

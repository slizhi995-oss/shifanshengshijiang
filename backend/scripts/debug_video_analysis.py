"""
调试视频分析功能
"""
import asyncio
import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings


async def check_dependencies():
    """检查依赖是否安装"""
    print("=" * 50)
    print("检查依赖...")
    print("=" * 50)
    
    # 检查 ffmpeg
    try:
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-version",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await proc.communicate()
        if proc.returncode == 0:
            print("✅ ffmpeg 已安装")
        else:
            print("❌ ffmpeg 未安装，请运行: brew install ffmpeg")
            return False
    except FileNotFoundError:
        print("❌ ffmpeg 未安装，请运行: brew install ffmpeg")
        return False
    
    # 检查 ffprobe
    try:
        proc = await asyncio.create_subprocess_exec(
            "ffprobe", "-version",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await proc.communicate()
        if proc.returncode == 0:
            print("✅ ffprobe 已安装")
        else:
            print("❌ ffprobe 未安装")
            return False
    except FileNotFoundError:
        print("❌ ffprobe 未安装")
        return False
    
    # 检查 opencv
    try:
        import cv2
        print(f"✅ opencv-python 已安装 (版本: {cv2.__version__})")
    except ImportError:
        print("❌ opencv-python 未安装，请运行: pip install opencv-python")
        return False
    
    # 检查 mediapipe
    try:
        import mediapipe
        print(f"✅ mediapipe 已安装 (版本: {mediapipe.__version__})")
    except ImportError:
        print("❌ mediapipe 未安装，请运行: pip install mediapipe")
        return False
    
    # 检查 httpx
    try:
        import httpx
        print(f"✅ httpx 已安装")
    except ImportError:
        print("❌ httpx 未安装，请运行: pip install httpx")
        return False
    
    return True


async def check_config():
    """检查配置"""
    print("\n" + "=" * 50)
    print("检查配置...")
    print("=" * 50)
    
    print(f"AI_PROVIDER: {settings.AI_PROVIDER}")
    print(f"DASHSCOPE_API_KEY: {'已配置' if settings.DASHSCOPE_API_KEY else '❌ 未配置'}")
    print(f"ENABLE_GESTURE_ANALYSIS: {settings.ENABLE_GESTURE_ANALYSIS}")
    print(f"VIDEO_ANALYSIS_PROVIDER: {settings.VIDEO_ANALYSIS_PROVIDER}")
    print(f"UPLOAD_DIR: {settings.UPLOAD_DIR}")
    
    if not settings.DASHSCOPE_API_KEY:
        print("\n❌ 请在 .env 中配置 DASHSCOPE_API_KEY")
        return False
    
    return True


async def test_video_analysis(video_path: str = None):
    """测试视频分析"""
    print("\n" + "=" * 50)
    print("测试视频分析...")
    print("=" * 50)
    
    # 查找测试视频
    if not video_path:
        upload_dir = settings.UPLOAD_DIR
        videos_dir = os.path.join(upload_dir, "videos")
        
        if os.path.exists(videos_dir):
            for f in os.listdir(videos_dir):
                if f.endswith(('.mp4', '.avi', '.mov')):
                    video_path = os.path.join(videos_dir, f)
                    break
    
    if not video_path or not os.path.exists(video_path):
        print("❌ 未找到测试视频文件")
        print(f"   请确保 {settings.UPLOAD_DIR}/videos/ 目录下有视频文件")
        return False
    
    print(f"测试视频: {video_path}")
    print(f"文件大小: {os.path.getsize(video_path) / 1024 / 1024:.2f} MB")
    
    from app.services.video_analysis_service import get_video_analysis_service
    
    service = get_video_analysis_service()
    
    try:
        # 测试获取视频时长
        print("\n1. 测试获取视频时长...")
        duration = await service._get_video_duration(video_path)
        print(f"   ✅ 视频时长: {duration:.2f} 秒")
        
        # 测试提取音频
        print("\n2. 测试提取音频...")
        audio_path = await service._extract_audio(video_path)
        print(f"   ✅ 音频已提取: {audio_path}")
        print(f"   音频大小: {os.path.getsize(audio_path) / 1024:.2f} KB")
        
        # 测试语音识别
        print("\n3. 测试语音识别...")
        transcript_result = await service._speech_to_text(video_path)
        print(f"   ✅ 识别文字: {transcript_result['text'][:100]}...")
        print(f"   分段数: {len(transcript_result.get('segments', []))}")
        
        # 测试动作分析
        if settings.ENABLE_GESTURE_ANALYSIS:
            print("\n4. 测试动作分析...")
            gesture_result = await service._analyze_gestures(video_path)
            if "error" in gesture_result:
                print(f"   ❌ 动作分析失败: {gesture_result['error']}")
            else:
                print(f"   ✅ 姿态得分: {gesture_result.get('posture_score')}")
                print(f"   ✅ 手势得分: {gesture_result.get('gesture_score')}")
                print(f"   ✅ 综合得分: {gesture_result.get('overall_gesture_score')}")
        
        # 完整分析
        print("\n5. 执行完整分析...")
        result = await service.analyze_video(video_path)
        print(f"   ✅ 分析完成!")
        print(f"   综合得分: {result['overall_score']}")
        print(f"   语速: {result['speech_rate']} 字/分钟")
        print(f"   停顿: {result['pause_count']} 次")
        print(f"   语气词: {result['filler_word_count']} 次")
        
        return True
        
    except Exception as e:
        print(f"\n❌ 分析失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    print("视频分析功能调试工具")
    print("=" * 50)
    
    # 检查依赖
    deps_ok = await check_dependencies()
    
    # 检查配置
    config_ok = await check_config()
    
    if deps_ok and config_ok:
        # 测试分析
        await test_video_analysis()
    else:
        print("\n请先解决上述问题后再测试")


if __name__ == "__main__":
    asyncio.run(main())

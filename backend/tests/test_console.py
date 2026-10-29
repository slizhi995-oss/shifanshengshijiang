import io

from app.core.console import configure_console_output


def test_console_output_supports_gbk_and_ascii(monkeypatch):
    stdout_bytes = io.BytesIO()
    stderr_bytes = io.BytesIO()
    stdout = io.TextIOWrapper(stdout_bytes, encoding="gbk")
    stderr = io.TextIOWrapper(stderr_bytes, encoding="ascii")
    monkeypatch.setattr("sys.stdout", stdout)
    monkeypatch.setattr("sys.stderr", stderr)

    configure_console_output()
    stdout.write("🚀 服务启动成功!\n")
    stderr.write("错误 🚀\n")
    stdout.flush()
    stderr.flush()

    assert stdout.encoding == "gbk"
    assert "服务启动成功!" in stdout_bytes.getvalue().decode("gbk")
    assert b"\\U0001f680" in stdout_bytes.getvalue()
    assert b"\\u9519\\u8bef" in stderr_bytes.getvalue()


def test_console_output_supports_captured_streams(monkeypatch):
    stdout, stderr = io.StringIO(), io.StringIO()
    monkeypatch.setattr("sys.stdout", stdout)
    monkeypatch.setattr("sys.stderr", stderr)

    configure_console_output()
    stdout.write("🚀 服务启动成功!")

    assert stdout.getvalue() == "🚀 服务启动成功!"

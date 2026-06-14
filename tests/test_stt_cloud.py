from tlgrm.stt import cloud


class _Resp:
    def __init__(self, payload):
        self._p = payload
    def raise_for_status(self):
        pass
    def json(self):
        return self._p


def _patch_post(monkeypatch, payload, capture):
    def fake_post(url, **kw):
        capture["url"] = url
        capture.update(kw)
        return _Resp(payload)
    monkeypatch.setattr(cloud.httpx, "post", fake_post)


def test_openai_transcribe(monkeypatch, tmp_path):
    f = tmp_path / "a.ogg"; f.write_bytes(b"x")
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    cap = {}
    _patch_post(monkeypatch, {"text": " hi "}, cap)
    assert cloud.openai_transcribe(str(f), None) == "hi"
    assert "audio/transcriptions" in cap["url"]
    assert cap["headers"]["Authorization"] == "Bearer k"


def test_deepgram_parses_nested_transcript(monkeypatch, tmp_path):
    f = tmp_path / "a.ogg"; f.write_bytes(b"x")
    monkeypatch.setenv("DEEPGRAM_API_KEY", "k")
    cap = {}
    payload = {"results": {"channels": [{"alternatives": [{"transcript": "hello"}]}]}}
    _patch_post(monkeypatch, payload, cap)
    assert cloud.deepgram_transcribe(str(f), None) == "hello"
    assert cap["headers"]["Authorization"] == "Token k"


def test_google_parses_results(monkeypatch, tmp_path):
    f = tmp_path / "a.ogg"; f.write_bytes(b"x")
    monkeypatch.setenv("GOOGLE_API_KEY", "k")
    cap = {}
    payload = {"results": [{"alternatives": [{"transcript": "hey"}]}]}
    _patch_post(monkeypatch, payload, cap)
    assert cloud.google_transcribe(str(f), None) == "hey"
    assert cap["headers"]["X-Goog-Api-Key"] == "k"
    assert "key=" not in cap["url"]


def test_missing_key_returns_none(monkeypatch, tmp_path):
    f = tmp_path / "a.ogg"; f.write_bytes(b"x")
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    assert cloud.elevenlabs_transcribe(str(f), None) is None


def test_deepgram_empty_channels_returns_none(monkeypatch, tmp_path):
    f = tmp_path / "a.ogg"; f.write_bytes(b"x")
    monkeypatch.setenv("DEEPGRAM_API_KEY", "k")
    _patch_post(monkeypatch, {"results": {"channels": []}}, {})
    assert cloud.deepgram_transcribe(str(f), None) is None

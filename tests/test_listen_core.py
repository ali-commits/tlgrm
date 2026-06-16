from tlgrm import listen_core as lc


def test_split_and_matches():
    assert lc._split_tokens(["@a,@b", "c"]) == ["@a", "@b", "c"]
    assert lc._matches({1}, set(), 1, 2, None, None) is True
    assert lc._matches(set(), {"x"}, 9, 8, "X", None) is True
    assert lc._matches({1}, {"x"}, 9, 8, "y", None) is False


def test_passes_allow_and_block():
    st = lc.ListenState()
    st.ids = {5}
    st.mode = "allow"
    assert lc._passes(st, chat_id=5, sender_id=0, cu=None, su=None) is True
    assert lc._passes(st, chat_id=9, sender_id=0, cu=None, su=None) is False
    st.mode = "block"
    assert lc._passes(st, chat_id=5, sender_id=0, cu=None, su=None) is False
    assert lc._passes(st, chat_id=9, sender_id=0, cu=None, su=None) is True


def test_should_transcribe_respects_enabled(monkeypatch):
    import tlgrm.stt.settings as s

    monkeypatch.setattr(s, "is_enabled", lambda: False)
    assert lc._should_transcribe("voice") is False
    monkeypatch.setattr(s, "is_enabled", lambda: True)
    assert lc._should_transcribe("voice") is True
    assert lc._should_transcribe("photo") is False

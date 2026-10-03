from datetime import UTC, datetime, timedelta

from app.store import Store


def test_question_text_is_not_stored_by_default():
    store = Store(":memory:")
    store.log_question("s1", "my secret formulation", jurisdiction="india")
    detail = store.activity("s1")[0]["detail"]
    assert "query" not in detail and detail["query_chars"] == len("my secret formulation")
    assert len(detail["query_sha256"]) == 64


def test_question_text_stored_when_enabled():
    store = Store(":memory:", store_query_text=True)
    store.log_question("s1", "my question")
    assert store.activity("s1")[0]["detail"]["query"] == "my question"


def test_latest_consent_wins():
    store = Store(":memory:")
    store.set_consent("s1", "manupatra", True)
    store.set_consent("s1", "manupatra", False)
    assert store.consents("s1") == {"manupatra": False}
    assert len([i for i in store.activity("s1") if i["type"] == "consent"]) == 2  # both decisions logged


def test_erase_only_touches_one_session():
    store = Store(":memory:")
    for sid in ("s1", "s2"):
        store.log_event(sid, "question", {})
        store.create_escalation(sid, "q", "india", None)
    assert store.erase("s1") == 2
    assert store.activity("s1") == [] and len(store.activity("s2")) == 2


def test_retention_purge(tmp_path):
    store = Store(tmp_path / "app.db")
    store.log_event("s1", "question", {})
    old = (datetime.now(UTC) - timedelta(days=100)).isoformat(timespec="seconds")
    store._db.execute("UPDATE audit_events SET ts = ?", (old,))
    store.log_event("s1", "question", {})
    assert store.purge_older_than(90) == 1
    assert len(store.activity("s1")) == 1

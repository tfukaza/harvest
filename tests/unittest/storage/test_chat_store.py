"""Tests for the ChatStore."""


from harvest.storage.schema.chat import ChatStore


def test_append_and_load_round_trip() -> None:
    store = ChatStore(database_url="sqlite:///:memory:")
    store.append_message("ch-1", 0, "agent-a", "hello")
    store.append_message("ch-1", 1, "agent-b", "hi back")

    messages = store.load_channel("ch-1")
    assert len(messages) == 2
    assert messages[0]["content"] == "hello"
    assert messages[1]["content"] == "hi back"


def test_messages_ordered_by_index() -> None:
    store = ChatStore(database_url="sqlite:///:memory:")
    store.append_message("ch-1", 2, "agent-a", "third")
    store.append_message("ch-1", 0, "agent-a", "first")
    store.append_message("ch-1", 1, "agent-a", "second")

    messages = store.load_channel("ch-1")
    assert [m["content"] for m in messages] == ["first", "second", "third"]


def test_list_channels_returns_distinct() -> None:
    store = ChatStore(database_url="sqlite:///:memory:")
    store.append_message("ch-1", 0, "agent-a", "hello")
    store.append_message("ch-2", 0, "agent-a", "hi")
    store.append_message("ch-1", 1, "agent-a", "again")

    channels = store.list_channels()
    assert sorted(channels) == ["ch-1", "ch-2"]


def test_channels_are_isolated() -> None:
    store = ChatStore(database_url="sqlite:///:memory:")
    store.append_message("ch-1", 0, "agent-a", "channel 1")
    store.append_message("ch-2", 0, "agent-b", "channel 2")

    assert len(store.load_channel("ch-1")) == 1
    assert len(store.load_channel("ch-2")) == 1
    assert store.load_channel("ch-1")[0]["sender_id"] == "agent-a"


def test_delete_channel() -> None:
    store = ChatStore(database_url="sqlite:///:memory:")
    store.append_message("ch-1", 0, "agent-a", "hello")
    store.delete_channel("ch-1")
    assert store.load_channel("ch-1") == []

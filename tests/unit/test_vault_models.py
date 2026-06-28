from src.vault.models import hash_key


def test_hash_key_deterministic():
    assert hash_key("cust_001") == hash_key("cust_001")


def test_hash_key_unique():
    assert hash_key("cust_001") != hash_key("cust_002")


def test_hash_key_composite():
    hk1 = hash_key("a", "b")
    hk2 = hash_key("b", "a")
    assert hk1 != hk2  # order matters

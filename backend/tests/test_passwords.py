from book_tracker.application.passwords import ScryptParameters, hash_password, verify_password


def test_scrypt_hash_verifies_and_uses_a_fresh_salt() -> None:
    first = hash_password("correct horse battery staple")
    second = hash_password("correct horse battery staple")

    assert first.digest != second.digest
    assert first.salt != second.salt
    assert verify_password("correct horse battery staple", first.digest, first.salt)
    assert not verify_password("wrong", first.digest, first.salt)


def test_stored_parameters_keep_an_old_hash_valid_after_the_default_changes() -> None:
    old = hash_password(
        "library secret",
        parameters=ScryptParameters(n=2**13, r=8, p=1, dklen=32),
    )

    assert "n=8192" in old.digest
    assert verify_password("library secret", old.digest, old.salt)

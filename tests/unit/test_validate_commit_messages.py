from scripts.validate_commit_messages import validate


def test_checks_every_message_in_pull_request():
    messages = [
        ("a" * 40, "feat: add patient endpoint"),
        ("b" * 40, "chore: update lock file"),
    ]

    errors = validate(messages)

    assert len(errors) == 1
    assert errors[0].startswith("bbbbbbbbbbbb")


def test_rejects_commit_body_and_trailers():
    message = "fix: validate patient access\n\nSigned-off-by: Patient"

    assert validate([("c" * 40, message)])

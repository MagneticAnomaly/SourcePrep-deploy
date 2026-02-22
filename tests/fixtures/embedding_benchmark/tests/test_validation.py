"""Tests for input validation utilities."""


def test_validate_email_accepts_valid():
    from src.validation import validate_email
    assert validate_email("user@example.com") == "user@example.com"


def test_validate_email_rejects_invalid():
    from src.validation import validate_email, ValidationError
    try:
        validate_email("not-an-email")
        assert False, "Should have raised"
    except ValidationError:
        pass


def test_validate_password_checks_complexity():
    from src.validation import validate_password
    assert validate_password("StrongPass1") is True


def test_sanitize_html_strips_tags():
    from src.validation import sanitize_html
    assert sanitize_html("<script>alert('xss')</script>hello") == "alert('xss')hello"


def test_validate_pagination_clamps_values():
    from src.validation import validate_pagination
    page, per_page, offset = validate_pagination(-1, 500, max_per_page=50)
    assert page == 1
    assert per_page == 50
    assert offset == 0

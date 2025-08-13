#!/usr/bin/env python3
"""
Basic tests for env_validator.validate_environment_variables().
Run with:  python test_env_validator.py
"""
import os
from contextlib import contextmanager

import env_validator


@contextmanager
def patched_env(**updates):
    """Temporarily patch os.environ within a context."""
    original = os.environ.copy()
    try:
        # Clear and apply only what we pass to make cases deterministic
        os.environ.clear()
        os.environ.update(updates)
        yield
    finally:
        os.environ.clear()
        os.environ.update(original)


def run_case(title, should_pass, **env):
    print(f"\n=== {title} ===")
    try:
        with patched_env(**env):
            env_validator.validate_environment_variables()
        if should_pass:
            print("OK: passed as expected.")
        else:
            print("ERROR: expected failure but passed.")
    except RuntimeError as e:
        if should_pass:
            print(f"ERROR: expected pass but failed: {e}")
        else:
            print("OK: failed as expected.")


def main():
    valid_env = dict(
        GEMINI_API_KEY="AIzaSy" + "X" * 40,
        MONGO_URI="mongodb+srv://user:pass@cluster.mongodb.net/db?retryWrites=true&w=majority",
        CORS_ORIGINS="https://ai-lawyer-tau.vercel.app,http://localhost:5000,http://127.0.0.1:5000",
        MAX_CONTENT_LENGTH="16777216",
        PORT="8080",
    )

    run_case("Valid environment", True, **valid_env)

    bad1 = valid_env.copy()
    bad1.pop("GEMINI_API_KEY")
    run_case("Missing GEMINI_API_KEY", False, **bad1)

    bad2 = valid_env.copy()
    bad2["MONGO_URI"] = "postgres://something"
    run_case("Invalid MONGO_URI scheme", False, **bad2)

    bad3 = valid_env.copy()
    bad3["CORS_ORIGINS"] = "localhost:5000,https://example.com"
    run_case("Bad CORS_ORIGINS entry", True, **bad3)  # warning only

    bad4 = valid_env.copy()
    bad4["MAX_CONTENT_LENGTH"] = "-10"
    run_case("Invalid MAX_CONTENT_LENGTH", True, **bad4)  # warning only


if __name__ == "__main__":
    main()

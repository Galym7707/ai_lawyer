#!/usr/bin/env python3
"""
Environment variable validator for the Kaz Legal Bot backend.

This module is imported by the Flask app on startup to make sure the
deployment has a minimal, sane configuration. It does **not** mutate
the environment – it only validates and prints friendly diagnostics.
"""
from __future__ import annotations

import os
import re
from typing import List


def _print_header(title: str) -> None:
    print(title)
    print("-" * max(60, len(title)))


def _print_block(kind: str, items: List[str]) -> None:
    if not items:
        return
    prefix = "WARNING" if kind == "warning" else "ERROR"
    for msg in items:
        print(f"{prefix}: {msg}")


def validate_environment_variables() -> bool:
    """
    Validate required/optional environment variables.

    Returns True on success. Raises RuntimeError on fatal configuration
    errors (missing required variables or clearly invalid values).
    """
    errors: List[str] = []
    warnings: List[str] = []

    # --- Required ---
    gemini_api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not gemini_api_key:
        errors.append("GEMINI_API_KEY is not set.")
    elif len(gemini_api_key) < 20:
        warnings.append("GEMINI_API_KEY looks unusually short – double-check it.")

    mongo_uri = os.getenv("MONGO_URI", "").strip()
    if not mongo_uri:
        errors.append("MONGO_URI is not set.")
    elif not re.match(r"^mongodb(\+srv)?:\/\/", mongo_uri):
        errors.append("MONGO_URI must start with 'mongodb://' or 'mongodb+srv://'.")

    # --- Optional / recommended ---
    cors_origins = os.getenv("CORS_ORIGINS", "").strip()
    if not cors_origins:
        warnings.append("CORS_ORIGINS is not set. The app will fall back to its built-in defaults.")
    else:
        bad: List[str] = []
        origins = [o.strip().rstrip("/") for o in cors_origins.split(",") if o.strip()]
        for origin in origins:
            if not re.match(r"^https?:\/\/", origin):
                bad.append(origin)
        if bad:
            warnings.append(f"CORS_ORIGINS contains non-URL entries: {', '.join(bad)}")

    max_content_len = os.getenv("MAX_CONTENT_LENGTH", "").strip()
    if not max_content_len:
        warnings.append("MAX_CONTENT_LENGTH is not set.")
    else:
        try:
            v = int(max_content_len)
            if v <= 0:
                raise ValueError
        except Exception:
            warnings.append(f"MAX_CONTENT_LENGTH must be a positive integer, got '{max_content_len}'.")

    port = os.getenv("PORT", "").strip()
    if port:
        try:
            p = int(port)
            if not (1 <= p <= 65535):
                raise ValueError
        except Exception:
            warnings.append(f"PORT must be a valid TCP port (1–65535), got '{port}'.")

    # --- Report ---
    if warnings:
        _print_header("WARNING: Environment Variable Warnings:")
        for w in warnings:
            print(f"   {w}")
        print("")

    if errors:
        _print_header("ERROR: Environment variable validation failed!")
        for e in errors:
            print(f"   {e}")
        print("")
        raise RuntimeError("Environment is not configured correctly.")

    print("SUCCESS: Environment variable validation successful!")
    return True


if __name__ == "__main__":
    try:
        validate_environment_variables()
    except RuntimeError as exc:
        import sys
        sys.stderr.write(str(exc) + "\n")
        raise

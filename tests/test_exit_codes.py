"""Exit code mapping regression tests."""

from xl.engine.dispatcher import error_envelope, exit_code_for


def test_exit_code_validation_class():
    env = error_envelope("x", "ERR_RANGE_INVALID", "bad ref")
    assert exit_code_for(env) == 10


def test_exit_code_protection_class():
    env = error_envelope("x", "ERR_PROTECTED_RANGE", "blocked")
    assert exit_code_for(env) == 20


def test_exit_code_formula_class():
    env = error_envelope("x", "ERR_FORMULA_BLOCKED", "blocked")
    assert exit_code_for(env) == 30


def test_exit_code_conflict_class():
    env = error_envelope("x", "ERR_PLAN_FINGERPRINT_CONFLICT", "stale")
    assert exit_code_for(env) == 40


def test_exit_code_io_class():
    env = error_envelope("x", "ERR_WORKBOOK_NOT_FOUND", "missing")
    assert exit_code_for(env) == 50


def test_exit_code_recalc_class():
    env = error_envelope("x", "ERR_RECALC_FAILED", "recalc")
    assert exit_code_for(env) == 60


def test_exit_code_unsupported_class():
    env = error_envelope("x", "ERR_UNSUPPORTED_OPERATION", "unsupported")
    assert exit_code_for(env) == 70


def test_exit_code_internal_fallback():
    env = error_envelope("x", "ERR_QUERY_FAILED", "unknown")
    assert exit_code_for(env) == 90

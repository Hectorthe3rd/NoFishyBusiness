import json
import os
import sys
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from eval.eval import check_health, run_test_case, main


def test_unreachable_backend_causes_nonzero_exit(capsys, monkeypatch):
    """When backend is unreachable, main() should exit with code 1 without running tests.
    
    Requirements: 13.2, 13.5
    """
    monkeypatch.setattr(sys, "argv", ["eval.py"])
    with patch("eval.eval.check_health", return_value=False):
        with pytest.raises(SystemExit) as exc_info:
            main()
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "could not be reached" in captured.out.lower() or "error" in captured.out.lower()


def test_failing_assertion_produces_fail_output_and_nonzero_exit(tmp_path, capsys, monkeypatch):
    """A failing assertion should produce [FAIL] output and exit with code 1.
    
    Requirements: 13.2, 13.5
    """
    monkeypatch.setattr(sys, "argv", ["eval.py"])
    # Create a test cases file with one failing case
    test_cases = [
        {
            "test_name": "failing_test",
            "endpoint": "/species",
            "method": "POST",
            "input": {"species_name": "Guppy"},
            "expected_label": "should return species info",
            "assert_keyword": "KEYWORD_THAT_WILL_NOT_BE_FOUND"
        }
    ]
    test_cases_file = tmp_path / "test_cases.json"
    test_cases_file.write_text(json.dumps(test_cases))

    # Mock the response — keyword won't be found so assertion fails
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.json.return_value = {"behavior": "Peaceful", "species_name": "Guppy"}

    with patch("eval.eval.check_health", return_value=True):
        with patch("eval.eval.TEST_CASES_PATH", str(test_cases_file)):
            with patch("requests.post", return_value=mock_resp):
                with pytest.raises(SystemExit) as exc_info:
                    main()

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "[FAIL]" in captured.out


def test_passing_assertion_produces_pass_output(tmp_path, capsys, monkeypatch):
    """A passing assertion should produce [PASS] output and zero exit.
    
    Requirements: 13.2, 13.5
    """
    monkeypatch.setattr(sys, "argv", ["eval.py"])
    test_cases = [
        {
            "test_name": "passing_test",
            "endpoint": "/species",
            "method": "POST",
            "input": {"species_name": "Guppy"},
            "expected_label": "should return species info",
            "assert_keyword": "behavior"
        }
    ]
    test_cases_file = tmp_path / "test_cases.json"
    test_cases_file.write_text(json.dumps(test_cases))

    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.json.return_value = {"behavior": "Peaceful", "species_name": "Guppy"}

    with patch("eval.eval.check_health", return_value=True):
        with patch("eval.eval.TEST_CASES_PATH", str(test_cases_file)):
            with patch("requests.post", return_value=mock_resp):
                main()  # Should not raise SystemExit

    captured = capsys.readouterr()
    assert "[PASS]" in captured.out
    assert "Passed: 1 / Total: 1" in captured.out

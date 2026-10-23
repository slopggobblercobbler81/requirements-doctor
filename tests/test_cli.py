"""Tests for CLI interface."""

import json
from requirements_doctor.cli import main


def test_cli_clean_file(tmp_path, capsys):
    req_file = tmp_path / "requirements.txt"
    req_file.write_text("click==8.1.3\nrequests==2.28.1\n", encoding="utf-8")

    code = main([str(req_file), "--check"])
    assert code == 0
    captured = capsys.readouterr()
    assert "All requirements healthy" in captured.out


def test_cli_dirty_file(tmp_path, capsys):
    req_file = tmp_path / "requirements.txt"
    req_file.write_text("requests==2.28.1\nrequests==2.25.0\n", encoding="utf-8")

    code = main([str(req_file), "--check"])
    assert code == 1
    captured = capsys.readouterr()
    assert "Duplicate entries found" in captured.out


def test_cli_json_output(tmp_path, capsys):
    req_file = tmp_path / "requirements.txt"
    req_file.write_text("requests==2.28.1\nrequests==2.25.0\n", encoding="utf-8")

    code = main([str(req_file), "--json"])
    assert code == 1
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert not data["clean"]
    assert len(data["reports"]) == 1
    assert data["reports"][0]["error_count"] > 0


def test_cli_fix(tmp_path, capsys):
    req_file = tmp_path / "requirements.txt"
    req_file.write_text("requests==2.25.0\nrequests==2.28.1\n", encoding="utf-8")

    code = main([str(req_file), "--fix"])
    assert code == 0
    captured = capsys.readouterr()
    assert "Fixed and formatted" in captured.out

    # Now verify clean
    code2 = main([str(req_file), "--check"])
    assert code2 == 0


def test_cli_diff(tmp_path, capsys):
    req_file = tmp_path / "requirements.txt"
    req_file.write_text("b==1.0.0\na==1.0.0\n", encoding="utf-8")

    code = main([str(req_file), "--diff"])
    assert code == 1  # diff exists
    captured = capsys.readouterr()
    assert "+a==1.0.0" in captured.out
    assert "-a==1.0.0" in captured.out


def test_cli_strict_pinning(tmp_path, capsys):
    req_file = tmp_path / "requirements.txt"
    req_file.write_text("requests>=2.28.0\n", encoding="utf-8")

    code_loose = main([str(req_file), "--allow-loose"])
    assert code_loose == 0

    code_strict = main([str(req_file), "--strict-pinning"])
    assert code_strict == 1


def test_cli_no_files_found(capsys, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    code = main([])
    assert code == 1
    captured = capsys.readouterr()
    assert "No requirements files specified" in captured.err


def test_cli_missing_specified_file(capsys):
    code = main(["non_existent_file.txt"])
    assert code == 1
    captured = capsys.readouterr()
    assert "File not found" in captured.err

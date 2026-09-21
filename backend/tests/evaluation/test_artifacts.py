import pytest
from pydantic import ValidationError

from app.evaluation.artifact_validator import validate_artifacts
from app.evaluation.context_builder import sha256
from app.evaluation.manifest import Manifest
from app.schemas.evaluation import ExecutableTestGenerationResult

PREFIX = ".specguard/generated_tests/"


def result(*files):
    return ExecutableTestGenerationResult.model_validate({"files": list(files)})


def test_normalization_and_hash(manifest, tmp_path):
    content = "def test_example():\r\n    assert True\r\n"
    artifacts = validate_artifacts(result({"path": PREFIX + "test_example.py", "content": content}), manifest, tmp_path)
    assert artifacts[0].content == content.replace("\r\n", "\n")
    assert artifacts[0].sha256 == sha256(artifacts[0].content.encode())
    assert artifacts[0].size_bytes == len(artifacts[0].content.encode())
    assert list(tmp_path.iterdir()) == []  # Validation itself never writes or executes.


@pytest.mark.parametrize("path", ["test_other.py", "tests/test_native.py", PREFIX + "conftest.py", PREFIX + "test_file.txt", PREFIX + "test_file.py.exe"])
def test_wrong_artifact_location_or_type(manifest, path):
    with pytest.raises(ValueError):
        validate_artifacts(result({"path": path, "content": "pass"}), manifest)


@pytest.mark.parametrize("content", ["def broken(:", "\x00", "+" * 10000 + "1"], ids=["syntax", "nul", "parser-depth"])
def test_invalid_python(manifest, content):
    with pytest.raises(ValueError, match="invalid Python syntax"):
        validate_artifacts(result({"path": PREFIX + "test_example.py", "content": content}), manifest)


def test_duplicate_case_insensitive_path(manifest):
    files = [{"path": PREFIX + name, "content": "pass"} for name in ("test_example.py", "test_EXAMPLE.py")]
    with pytest.raises(ValueError, match="duplicate"):
        validate_artifacts(result(*files), manifest)


@pytest.mark.parametrize("limits, files", [
    ({"max_files": 1, "max_file_bytes": 100, "max_total_bytes": 200}, 2),
    ({"max_files": 2, "max_file_bytes": 3, "max_total_bytes": 6}, 1),
    ({"max_files": 2, "max_file_bytes": 4, "max_total_bytes": 6}, 2),
])
def test_artifact_limits(manifest, limits, files):
    data = manifest.model_dump()
    data["artifacts"] = limits
    restricted = Manifest.model_validate(data)
    outputs = [{"path": PREFIX + f"test_{i}.py", "content": "pass"} for i in range(files)]
    with pytest.raises(ValueError):
        validate_artifacts(result(*outputs), restricted)


def test_symlink_and_existing_artifact(manifest, tmp_path):
    output = result({"path": PREFIX + "test_example.py", "content": "pass"})
    directory = tmp_path / PREFIX
    directory.mkdir(parents=True)
    (directory / "test_example.py").write_text("existing")
    with pytest.raises(ValueError, match="overwrite"):
        validate_artifacts(output, manifest, tmp_path)
    (directory / "test_example.py").unlink()
    (directory / "test_example.py").symlink_to(tmp_path / "missing")
    with pytest.raises(ValueError, match="symlinks"):
        validate_artifacts(output, manifest, tmp_path)


def test_schema_rejects_empty_and_unknown_fields():
    with pytest.raises(ValidationError):
        result()
    with pytest.raises(ValidationError):
        result({"path": PREFIX + "test_example.py", "content": "pass", "execute": True})


def test_validation_does_not_execute_python(manifest, tmp_path):
    marker = tmp_path / "must-not-exist"
    code = f"from pathlib import Path\nPath({str(marker)!r}).write_text('executed')\n"
    validate_artifacts(result({"path": PREFIX + "test_example.py", "content": code}), manifest)
    assert not marker.exists()

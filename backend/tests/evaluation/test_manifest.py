import pytest
from pydantic import ValidationError

from app.evaluation.manifest import Manifest, load_manifest
from app.evaluation.paths import safe_path, validate_relative_path


def test_manifest_round_trip(manifest):
    assert Manifest.model_validate_json(manifest.model_dump_json()) == manifest
    assert manifest.repository.commit == "aeb8c2ba30521204c17e9843141f8e118dc5bc21"
    assert manifest.context.mode == "spec_plus_code"


@pytest.mark.parametrize("path", [
    "", "/tmp/test.py", "../test.py", "tests/../test.py", "tests/./test.py", "tests//test.py",
    "tests/", "C:/test.py", "C:\\test.py", "\\\\server\\share", "~/test.py",
    "tests/%2e%2e/test.py", "tests/test.py\x00", "tests/test.py\n", ".git/config", ".env", ".env.local",
])
def test_unsafe_paths(path):
    with pytest.raises(ValueError):
        validate_relative_path(path)


@pytest.mark.parametrize("parts, value", [
    (("schema_version",), 2), (("schema_version",), True), (("schema_version",), "1"),
    (("language",), "javascript"), (("unknown",), "ignored?"),
    (("repository", "commit"), "main"), (("repository", "commit"), "a" * 39),
    (("repository", "commit"), "A" * 40), (("repository", "bundle"), "../target.bundle"),
    (("environment", "python_version"), "3.13"), (("environment", "dependency_lock"), "/etc/passwd"),
    (("environment", "install_command"), "pip install something"),
    (("environment", "install_command"), ["bash", "-c", "echo hello"]),
    (("environment", "install_command"), ["python", "\x00"]),
    (("tests", "baseline_command"), ["python", "-c", "print(1)"]),
    (("tests", "baseline_command"), ["pytest", "tests", "generated"]),
    (("tests", "baseline_command"), ["pytest", "--override-ini", "addopts=tests"]),
    (("tests", "native_paths"), []), (("tests", "generated_path"), "src"),
    (("tests", "repeat_count"), 1), (("tests", "timeout_seconds"), 0),
    (("tests", "native_paths"), ["tests", "tests"]),
    (("context", "mode"), "spec_only"), (("context", "source_files"), ["tests/test_native.py"]),
    (("context", "source_files"), []), (("context", "source_files"), ["src/readme.md"]),
    (("mutation", "source_paths"), ["tests"]), (("mutation", "timeout_seconds"), -1),
    (("limits", "memory_mb"), 0), (("limits", "memory_mb"), "1024"),
    (("limits", "pids"), True), (("limits", "cpus"), 0.0),
    (("limits", "output_kb"), 0), (("limits", "scratch_mb"), 0),
    (("limits", "file_size_mb"), 0), (("limits", "pids"), 513),
    (("artifacts", "max_files"), 0), (("artifacts", "max_total_bytes"), 1),
    (("generation", "prompt_version"), ""), (("generation", "temperature"), 3.0),
    (("generation", "provider"), "unknown"), (("generation", "seed"), -1),
])
def test_invalid_manifest_fields(manifest, parts, value):
    data = manifest.model_dump()
    node = data
    for part in parts[:-1]:
        node = node[part]
    node[parts[-1]] = value
    with pytest.raises(ValidationError):
        Manifest.model_validate(data)


@pytest.mark.parametrize("url", [
    "http://github.com/org/repo.git", "ssh://github.com/org/repo.git", "file:///tmp/repo.git",
    "https://user:secret@github.com/org/repo.git", "https://github.com/org/repo.git?token=secret",
    "https://github.com/org/repo.git#main", "https://github.com:123/org/repo.git",
    "https://github.com/org/../repo.git", "https://github.com/org/repo", "https://localhost/org/repo.git",
])
def test_invalid_repository_urls(manifest, url):
    data = manifest.model_dump()
    data["repository"] = {"url": url, "commit": manifest.repository.commit}
    with pytest.raises(ValidationError):
        Manifest.model_validate(data)


def test_https_repository_contract(manifest):
    data = manifest.model_dump()
    data["repository"] = {"url": "https://github.com/example/project.git", "commit": "a" * 40}
    assert Manifest.model_validate(data).repository.url == data["repository"]["url"]
    data["repository"]["bundle"] = "target.bundle"
    with pytest.raises(ValidationError):
        Manifest.model_validate(data)


def test_spec_only_mode(manifest):
    data = manifest.model_dump()
    data["context"].update(mode="spec_only", source_files=[])
    assert Manifest.model_validate(data).context.source_files == []


@pytest.mark.parametrize("yaml", [
    "schema_version: 1\nschema_version: 1\n", "schema_version: &v 1\nlanguage: *v\n",
    "!!python/object/apply:os.system ['echo unsafe']", "[unclosed", "x" * 65537,
])
def test_malformed_yaml(tmp_path, yaml):
    path = tmp_path / "manifest.yaml"
    path.write_text(yaml)
    with pytest.raises(ValueError):
        load_manifest(path)


def test_manifest_requires_utf8(tmp_path):
    path = tmp_path / "manifest.yaml"
    path.write_bytes("schema_version: 1".encode("utf-16"))
    with pytest.raises(ValueError, match="UTF-8"):
        load_manifest(path)


@pytest.mark.parametrize("outside", [True, False])
def test_symlink_components_rejected(tmp_path, outside):
    root = tmp_path / "workspace"
    root.mkdir()
    target = tmp_path / "other" if outside else root / "inside"
    target.mkdir()
    (root / "link").symlink_to(target, target_is_directory=True)
    with pytest.raises(ValueError, match="symlinks"):
        safe_path(root, "link/test_example.py")


def test_missing_and_safe_paths(tmp_path):
    assert safe_path(tmp_path, "new/test_example.py") == tmp_path / "new/test_example.py"
    with pytest.raises(ValueError, match="does not exist"):
        safe_path(tmp_path, "missing", must_exist=True)

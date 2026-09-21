import json
import shutil
import subprocess
import sys

import pytest

from app.evaluation.context_builder import build_context
from app.evaluation.manifest import Manifest
from app.evaluation.prepare import prepare
from app.evaluation import snapshot
from app.schemas.evaluation import EvaluationReport


def test_reproducible_offline_preparation(subject, tmp_path):
    runs = []
    for name in ("first", "second"):
        output = tmp_path / name
        report = prepare(subject / "specguard.yaml", output, fixture=subject / "generation-fixture.json")
        assert report.status == "prepared"
        assert report.generation.successful is None
        assert report.native.collection_status == "not_run"
        assert report.generated.mutation is None
        assert report.provenance.runner_image_digest is None
        assert EvaluationReport.model_validate_json((output / "report.json").read_text()) == report
        assert not list(output.rglob(".git"))
        for path in (subject / "target").rglob("*"):
            if path.is_file():
                assert (output / "target" / path.relative_to(subject / "target")).read_bytes() == path.read_bytes()
        artifact = report.artifacts[0]
        assert (output / "generated" / artifact.path).is_file()
        context = json.loads((output / "context.json").read_text())
        assert list(context["source_files"]) == ["src/reservations.py"]
        assert "test_quote_invalid_range" not in (output / "context.json").read_text()
        runs.append(report)
    assert runs[0].run_id != runs[1].run_id
    assert runs[0].provenance == runs[1].provenance
    assert runs[0].artifacts == runs[1].artifacts


def test_bundle_revision_is_reproducible(subject, tmp_path):
    copied = tmp_path / "subject"
    shutil.copytree(subject, copied)
    result = subprocess.run([sys.executable, str(copied / "rebuild_bundle.py")], capture_output=True, check=True, text=True, timeout=30)
    assert result.stdout.strip() == "aeb8c2ba30521204c17e9843141f8e118dc5bc21"
    snapshot.export_bundle(copied / "target.bundle", result.stdout.strip(), tmp_path / "export")
    assert (tmp_path / "export/src/reservations.py").read_bytes() == (subject / "target/src/reservations.py").read_bytes()


def test_existing_output_is_never_overwritten(subject, tmp_path):
    output = tmp_path / "run"
    output.mkdir()
    (output / "keep").write_text("user data")
    with pytest.raises(ValueError, match="new directory"):
        prepare(subject / "specguard.yaml", output)
    assert (output / "keep").read_text() == "user data"


def test_invalid_fixture_leaves_no_partial_output(subject, tmp_path):
    fixture = tmp_path / "invalid.json"
    fixture.write_text('{"files": [{"path": "tests/test_native.py", "content": "pass"}]}')
    with pytest.raises(ValueError, match="generated directory"):
        prepare(subject / "specguard.yaml", tmp_path / "run", fixture=fixture)
    assert not (tmp_path / "run").exists()
    assert not list(tmp_path.glob(".specguard-prepare-*"))


def test_missing_commit_cannot_prepare(subject, manifest, tmp_path):
    with pytest.raises(ValueError, match="bundle"):
        snapshot.export_bundle(subject / "target.bundle", "0" * 40, tmp_path / "target")
    assert not (tmp_path / "target").exists()


def test_spec_only_context_excludes_all_source(subject, manifest):
    data = manifest.model_dump()
    data["context"].update(mode="spec_only", source_files=[])
    context = build_context(Manifest.model_validate(data), subject, subject / "target")
    assert context["source_files"] == {}
    assert "def quote" not in context["specification"]


def test_context_rejects_symlink_source(subject, manifest, tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src/reservations.py").symlink_to(subject / "target/tests/test_native.py")
    with pytest.raises(ValueError, match="symlinks"):
        build_context(manifest, subject, tmp_path)


@pytest.mark.parametrize("entry", [
    b"120000 blob abc\tlink\0", b"160000 commit abc\tsubmodule\0",
    b"100644 blob abc\t../escape.py\0", b"100644 blob abc\t.git/config\0",
    b"100644 blob abc\t.env\0", b"100644 blob abc\t/absolute\0",
])
def test_snapshot_rejects_unsafe_tree_entries(tmp_path, monkeypatch, entry):
    bundle = tmp_path / "unsafe.bundle"
    bundle.write_bytes(b"fake fixture")

    def fake_git(*args, **kwargs):
        if args[0] == "ls-tree":
            return entry
        if args[:2] == ("cat-file", "-t"):
            return b"commit"
        return b""

    monkeypatch.setattr(snapshot, "git", fake_git)
    with pytest.raises(ValueError):
        snapshot.export_bundle(bundle, "a" * 40, tmp_path / "target")
    assert not (tmp_path / "target").exists()


def test_preparation_cli(subject, tmp_path):
    command = [sys.executable, "-m", "app.evaluation.prepare", str(subject / "specguard.yaml"), "--output", str(tmp_path / "run")]
    result = subprocess.run(command, capture_output=True, text=True, check=True, timeout=30)
    assert json.loads(result.stdout)["status"] == "prepared"
    second = subprocess.run(command, capture_output=True, text=True, timeout=30)
    assert second.returncode == 2 and "new directory" in second.stderr

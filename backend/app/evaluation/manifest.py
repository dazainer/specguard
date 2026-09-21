"""Version 1 manifest for trusted, curated Python benchmarks."""

import re
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urlsplit

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.evaluation.paths import RelativePath, overlap


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


CommitSHA = Annotated[str, Field(pattern=r"^[0-9a-f]{40}$")]
SHA256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class Repository(StrictModel):
    commit: CommitSHA
    url: str | None = None
    bundle: RelativePath | None = None

    @field_validator("url")
    @classmethod
    def https_git_url(cls, value):
        if value is None:
            return value
        parsed = urlsplit(value)
        if (
            parsed.scheme != "https" or not parsed.hostname
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.port not in (None, 443)
            or not re.fullmatch(r"[A-Za-z0-9.-]+", parsed.hostname)
            or "." not in parsed.hostname
            or not re.fullmatch(r"/(?:[A-Za-z0-9_-]+/)+[A-Za-z0-9_.-]+\.git", parsed.path)
            or any(part in {".", ".."} for part in parsed.path.split("/"))
        ):
            raise ValueError("repository URL must be credential-free HTTPS ending in .git")
        return value

    @model_validator(mode="after")
    def one_source(self):
        if (self.url is None) == (self.bundle is None):
            raise ValueError("declare exactly one repository source: url or bundle")
        if self.bundle and not self.bundle.endswith(".bundle"):
            raise ValueError("local repository must be a .bundle file")
        return self


def validate_command(command: list[str], *, optional: bool = False) -> list[str]:
    if not command and optional:
        return command
    if not command or len(command) > 64:
        raise ValueError("command must be a nonempty argument array of at most 64 items")
    if any(not arg or len(arg) > 1024 or any(ord(char) < 32 or ord(char) == 127 for char in arg) for arg in command):
        raise ValueError("command arguments must be nonempty and contain no control characters")
    if command[0] not in {"python", "python3", "pytest", "uv"}:
        raise ValueError("unsupported executable; shell command interpreters are not allowed")
    return command


class Specification(StrictModel):
    path: RelativePath


class Environment(StrictModel):
    python_version: Literal["3.12"]
    dependency_lock: RelativePath
    install_command: list[str] = Field(default_factory=list)

    @field_validator("install_command")
    @classmethod
    def trusted_install(cls, value):
        return validate_command(value, optional=True)


class Context(StrictModel):
    mode: Literal["spec_only", "spec_plus_code"]
    interface_path: RelativePath
    source_files: list[RelativePath] = Field(default_factory=list, max_length=32)

    @model_validator(mode="after")
    def source_visibility(self):
        if self.mode == "spec_only" and self.source_files:
            raise ValueError("spec_only context cannot expose source files")
        if self.mode == "spec_plus_code" and not self.source_files:
            raise ValueError("spec_plus_code context requires explicit source files")
        if len(set(self.source_files)) != len(self.source_files):
            raise ValueError("context source files must be unique")
        if any(not path.endswith(".py") for path in self.source_files):
            raise ValueError("context source files must be Python modules")
        return self


class Tests(StrictModel):
    native_paths: list[RelativePath] = Field(min_length=1, max_length=32)
    generated_path: RelativePath
    baseline_command: list[str]
    timeout_seconds: int = Field(default=60, ge=1, le=600)
    repeat_count: int = Field(default=2, ge=2, le=10)

    @field_validator("baseline_command")
    @classmethod
    def pytest_command(cls, value):
        validate_command(value)
        prefix = 1 if value[:1] == ["pytest"] else 3
        if prefix == 3 and value[:3] not in (["python", "-m", "pytest"], ["python3", "-m", "pytest"]):
            raise ValueError("baseline command must invoke pytest")
        # Paths are supplied by the runner so native/generated suites stay separate.
        if any(arg not in {"-q", "-v", "--strict-markers", "--strict-config"} for arg in value[prefix:]):
            raise ValueError("baseline command may only contain supported display/strictness flags; paths are separate")
        return value


class Mutation(StrictModel):
    source_paths: list[RelativePath] = Field(min_length=1, max_length=32)
    excluded_paths: list[RelativePath] = Field(default_factory=list, max_length=32)
    timeout_seconds: int = Field(default=120, ge=1, le=600)


class ResourceLimits(StrictModel):
    memory_mb: int = Field(default=1024, ge=64, le=16384)
    cpus: float = Field(default=1.0, ge=0.1, le=8.0)
    pids: int = Field(default=128, ge=16, le=512)
    output_kb: int = Field(default=1024, ge=1, le=16384)
    scratch_mb: int = Field(default=128, ge=16, le=4096)
    file_size_mb: int = Field(default=16, ge=1, le=1024)


class ArtifactLimits(StrictModel):
    max_files: int = Field(default=10, ge=1, le=20)
    max_file_bytes: int = Field(default=65536, ge=1, le=262144)
    max_total_bytes: int = Field(default=262144, ge=1, le=1048576)

    @model_validator(mode="after")
    def coherent_sizes(self):
        if self.max_file_bytes > self.max_total_bytes:
            raise ValueError("per-file limit cannot exceed total artifact limit")
        return self


class GenerationConfig(StrictModel):
    provider: Literal["fixture", "openai"]
    model: str = Field(min_length=1, max_length=128)
    prompt_version: str = Field(min_length=1, max_length=128)
    temperature: float = Field(ge=0, le=2)
    seed: int | None = Field(default=None, ge=0)


class Manifest(StrictModel):
    schema_version: Literal[1]
    language: Literal["python"]
    repository: Repository
    specification: Specification
    environment: Environment
    context: Context
    tests: Tests
    mutation: Mutation
    limits: ResourceLimits
    artifacts: ArtifactLimits = Field(default_factory=ArtifactLimits)
    generation: GenerationConfig

    @field_validator("schema_version", mode="before")
    @classmethod
    def integer_version(cls, value):
        if type(value) is not int:
            raise ValueError("schema_version must be an integer")
        return value

    @model_validator(mode="after")
    def separate_inputs(self):
        native = self.tests.native_paths
        generated = self.tests.generated_path
        source = self.context.source_files + self.mutation.source_paths
        for paths in [native, self.mutation.source_paths, self.mutation.excluded_paths]:
            if len(paths) != len(set(paths)):
                raise ValueError("declared path lists must not contain duplicates")
        if any(overlap(generated, path) for path in native + source + [self.environment.dependency_lock]):
            raise ValueError("generated directory must be separate from native tests and source")
        if any(overlap(test, path) for test in native for path in source):
            raise ValueError("native tests must not be visible source or mutation targets")
        if self.specification.path == self.context.interface_path:
            raise ValueError("specification and public interface must be separate files")
        return self


class UniqueKeyLoader(yaml.SafeLoader):
    def construct_mapping(self, node, deep=False):
        mapping = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if not isinstance(key, str) or key in mapping:
                raise ValueError("YAML keys must be unique strings")
            mapping[key] = self.construct_object(value_node, deep=deep)
        return mapping


def load_manifest(path: Path) -> Manifest:
    if path.is_symlink():
        raise ValueError("manifest must not be a symlink")
    with path.open("rb") as file:
        raw = file.read(65537)
    if len(raw) > 65536:
        raise ValueError("manifest exceeds 64 KiB")
    try:
        text = raw.decode("utf-8")
        # Anchors/aliases and custom tags add no value to this deliberately small contract.
        if any(isinstance(token, (yaml.tokens.AnchorToken, yaml.tokens.AliasToken, yaml.tokens.TagToken)) for token in yaml.scan(text)):
            raise ValueError("YAML anchors, aliases, and explicit tags are not supported")
        return Manifest.model_validate(yaml.load(text, Loader=UniqueKeyLoader))
    except (yaml.YAMLError, UnicodeError, RecursionError) as error:
        raise ValueError("invalid UTF-8 YAML manifest") from error

import pytest

from midi_sampling.sampling.exceptions import (
    DefinitionReferenceError,
    DuplicateDefinitionIdError,
)

from conftest import (
    DEFAULT_SESSION_YAML,
    DEFAULT_TONE_YAML,
    make_session,
    resolve_session,
)


class TestReferenceResolution:
    def test_relative_paths_resolved_from_referencing_file(self, tmp_path):
        session = resolve_session(make_session(tmp_path))
        tone = session.tones[0]
        # tones/tone1.yaml references ../presets/zones.yaml
        assert tone.zones[0].low == 36
        assert tone.velocity_layers[0].send == 48

    def test_initialization_files_resolved_in_order(self, tmp_path):
        session_yaml = DEFAULT_SESSION_YAML.replace(
            "initialization_files: []",
            "initialization_files:\n    - midi/reset.mid\n    - midi/setup.mid",
        )
        session_path = make_session(
            tmp_path,
            session_yaml=session_yaml,
            extra_files={"midi/reset.mid": "", "midi/setup.mid": ""},
        )
        session = resolve_session(session_path)
        assert [p.name for p in session.initialization_files] == [
            "reset.mid",
            "setup.mid",
        ]

    def test_missing_reference_rejected(self, tmp_path):
        tone_yaml = DEFAULT_TONE_YAML.replace(
            "../presets/zones.yaml", "../presets/does_not_exist.yaml"
        )
        session_path = make_session(tmp_path, tone_yaml=tone_yaml)
        with pytest.raises(DefinitionReferenceError):
            resolve_session(session_path)

    def test_wrong_kind_rejected(self, tmp_path):
        tone_yaml = DEFAULT_TONE_YAML.replace(
            "../presets/zones.yaml", "../presets/velocities.yaml"
        )
        session_path = make_session(tmp_path, tone_yaml=tone_yaml)
        with pytest.raises(DefinitionReferenceError) as excinfo:
            resolve_session(session_path)
        assert "kind" in str(excinfo.value)

    def test_absolute_path_rejected(self, tmp_path):
        absolute = (tmp_path / "presets" / "zones.yaml").as_posix()
        tone_yaml = DEFAULT_TONE_YAML.replace("../presets/zones.yaml", absolute)
        session_path = make_session(tmp_path, tone_yaml=tone_yaml)
        with pytest.raises(DefinitionReferenceError):
            resolve_session(session_path)

    def test_url_rejected(self, tmp_path):
        tone_yaml = DEFAULT_TONE_YAML.replace(
            "../presets/zones.yaml", "https://example.com/zones.yaml"
        )
        session_path = make_session(tmp_path, tone_yaml=tone_yaml)
        with pytest.raises(DefinitionReferenceError):
            resolve_session(session_path)

    def test_home_expansion_rejected(self, tmp_path):
        tone_yaml = DEFAULT_TONE_YAML.replace(
            "../presets/zones.yaml", "~/zones.yaml"
        )
        session_path = make_session(tmp_path, tone_yaml=tone_yaml)
        with pytest.raises(DefinitionReferenceError):
            resolve_session(session_path)

    def test_glob_rejected(self, tmp_path):
        tone_yaml = DEFAULT_TONE_YAML.replace(
            "../presets/zones.yaml", "../presets/*.yaml"
        )
        session_path = make_session(tmp_path, tone_yaml=tone_yaml)
        with pytest.raises(DefinitionReferenceError):
            resolve_session(session_path)

    def test_duplicate_definition_id_rejected(self, tmp_path):
        session_yaml = DEFAULT_SESSION_YAML.replace(
            "definitions:\n  - file: tones/tone1.yaml",
            "definitions:\n  - file: tones/tone1.yaml\n  - file: tones/tone2.yaml",
        )
        session_path = make_session(
            tmp_path,
            session_yaml=session_yaml,
            extra_files={"tones/tone2.yaml": DEFAULT_TONE_YAML},
        )
        with pytest.raises(DuplicateDefinitionIdError):
            resolve_session(session_path)

    def test_yml_extension_accepted(self, tmp_path):
        tone_yaml = DEFAULT_TONE_YAML.replace(
            "../presets/zones.yaml", "../presets/zones.yml"
        )
        session_path = make_session(tmp_path, tone_yaml=tone_yaml)
        zones_source = (tmp_path / "presets" / "zones.yaml").read_text(encoding="utf-8")
        (tmp_path / "presets" / "zones.yml").write_text(zones_source, encoding="utf-8")
        session = resolve_session(session_path)
        assert session.tones[0].zones[0].low == 36

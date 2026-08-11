from seasenselib.pipeline.config import PipelineConfig


def test_pipeline_profiles_have_descriptions():
    for name in ("minimal", "default", "full"):
        cfg = PipelineConfig.from_resource(name)
        description = cfg.global_config.get("description")
        assert description, f"Profile '{name}' missing description"


def test_default_profile_unit_handling_handlers():
    cfg = PipelineConfig.from_resource("default")
    stage = next((s for s in cfg.pipeline if s.name == "unit_handling"), None)
    assert stage is not None
    handlers = stage.config.get("handlers", [])
    assert "normalize" in handlers
    assert "conductivity_normalize" in handlers
    assert "convert" not in handlers


def test_default_profile_includes_reader_transformation_after_unit_handling():
    cfg = PipelineConfig.from_resource("default")
    stage_names = [stage.name for stage in cfg.pipeline]

    assert stage_names.index("unit_handling") + 1 == stage_names.index(
        "transformation"
    )
    stage = next((s for s in cfg.pipeline if s.name == "transformation"), None)
    assert stage is not None
    assert stage.config.get("handlers") == ["reader"]


def test_full_profile_includes_all_stages():
    cfg = PipelineConfig.from_resource("full")
    stage_names = [stage.name for stage in cfg.pipeline]
    assert stage_names == [
        "mapping",
        "unit_handling",
        "transformation",
        "derivation",
        "metadata_extraction",
        "metadata_enrichment",
        "validation",
        "finalization",
    ]

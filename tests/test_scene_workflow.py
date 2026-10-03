from __future__ import annotations

from pathlib import Path
import base64
import json

import run_scene_workflow
import workflow_server
from scene_workflow import agent_reach_channels
from scene_workflow.agent_reach_channels import _baike_terms
from scene_workflow.production_modeling_standard import modeling_standard
from scene_workflow.research_to_prompt import build_prompt_quality_package
from scene_workflow.scene_brief import blender_skill_prompt, fallback_brief, parse_json


def test_parse_json_fence() -> None:
    assert parse_json("```json\n{\"ok\": true}\n```")["ok"] is True


def test_fallback_brief_and_skill_prompt(tmp_path: Path) -> None:
    brief = fallback_brief("做一个咖啡店室内场景", [])
    prompt = blender_skill_prompt(brief, tmp_path, [])
    assert brief["mode"] == "concept_spatial_modeling"
    assert brief["envelope_model"] == "continuous_shell_with_explicit_openings"
    assert "skirting_or_baseboard" in brief["hard_finish"]["required"]
    assert "CLOSED-SPACE GATE" in prompt
    assert "HARD FINISH SCOPE" in prompt
    assert "blender-mcp-reference-modeling" in prompt


def test_exterior_module_requires_structural_audit(tmp_path: Path) -> None:
    brief = fallback_brief("生成祈年殿外观，重点屋顶、台基、楼梯和栏杆", [], "exterior")
    package = build_prompt_quality_package("生成祈年殿外观", {"sources": []}, brief, modeling_standard("exterior_architecture"))
    brief["prompt_quality_package"] = package
    prompt = blender_skill_prompt(brief, tmp_path, [])
    assert brief["generation_module"] == "exterior_architecture"
    assert brief["envelope_model"] == "assembled_elements_with_verified_joints"
    assert "EXTERIOR STRUCTURE GATE" in prompt
    assert "STAIR AND BALUSTRADE GATE" in prompt
    assert "NO FILLER LANDSCAPE" in prompt
    assert "提示词配方" in prompt
    assert "staged exterior execution plan" in prompt
    assert "RESEARCH TO MODEL PROMPT PACKAGE" in prompt
    assert "material targets" in prompt
    assert "no rails crossing stair openings" in prompt


def test_fallback_does_not_guess_exterior_module() -> None:
    brief = fallback_brief("生成祈年殿外观", [])
    assert brief["generation_module"] == "interior_space"


def test_fallback_brief_is_generic_for_meeting_room() -> None:
    brief = fallback_brief("会议室，封闭空间，包含门窗和基础硬装", [])
    assert brief["spaces"] == [{"name": "meeting room", "type": "room"}]
    assert brief["spatial_envelope"]["mode"] == "closed"


def test_run_writes_actual_workflow_manifest(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(run_scene_workflow, "RUNS", tmp_path)
    case_dir = run_scene_workflow.run("生成祈年殿外观，重点楼梯和栏杆", "case", offline=True, module="exterior", auto_build=False)
    manifest = json.loads((case_dir / "workflow_manifest.json").read_text(encoding="utf-8"))
    statuses = {item["name"]: item["status"] for item in manifest["stages"]}
    assert statuses["research_package"] == "complete"
    assert statuses["scene_brief"] == "failed"
    assert "research_to_prompt" not in statuses
    assert not (case_dir / "prompt_quality_package.json").exists()
    assert not (case_dir / "skill_prompt.md").exists()


def test_research_is_converted_to_modeling_prompt_package() -> None:
    brief = fallback_brief("生成一个现实风格地标外观", [], "exterior")
    research = {
        "sources": [
            {
                "title": "Example landmark facade",
                "url": "https://example.test",
                "snippet": "The building has marble stairs, red timber columns, glazed roof tiles and gold trim.",
            }
        ]
    }
    package = build_prompt_quality_package("生成一个现实风格地标外观", research, brief, modeling_standard("exterior_architecture"))
    assert package["identity_lock"]["do_not_replace_target"] is True
    assert "stairs with real treads, risers, landings and rail openings" in package["detail_targets"]
    assert {"stone", "timber", "roof_tile", "metal"}.issubset(set(package["material_targets"]))
    assert package["evidence_for_prompt"][0]["usable_for_prompt"].startswith("The building has")


def test_landmark_signature_words_become_geometry_rules() -> None:
    brief = fallback_brief("生成故宫角楼外观", [], "exterior")
    package = build_prompt_quality_package(
        "生成故宫角楼外观，三层复合屋顶，黄色琉璃瓦，斗拱，菱花门窗，汉白玉栏杆，台基和城墙连接",
        {"sources": []},
        brief,
        modeling_standard("exterior_architecture"),
    )
    names = {item["name"] for item in package["signature_feature_rules"]}
    assert {"compound_roof_and_tiles", "dougong_brackets", "ornamental_lattice_windows", "stone_balustrade_and_stairs", "plinth_wall_ground_connection"}.issubset(names)
    lines = "\n".join(item for feature in package["signature_feature_rules"] for item in feature["rules"])
    assert "roof cannot be a single flat slab" in lines
    assert "no upper roof may float above empty air" in lines
    assert "do not leave visible shadow gaps under the building" in lines
    assert "windows need recessed dark glass" in lines


def test_tiananmen_prompt_package_gets_geometry_contract() -> None:
    brief = {
        "generation_module": "exterior_architecture",
        "scene_goal": "Tiananmen Gate exterior",
        "space_contracts": [
            {
                "space": "city platform",
                "vertical_geometry": ["1.59m white marble xumizuo base", "13m red brick core"],
                "openings": ["five arched gateways"],
            }
        ],
        "must_have": ["double-eaved xieshan roof", "five arched gateways", "36 lattice windows"],
        "relationships": ["upper pavilion centered on city platform"],
        "delivery_views": [],
    }
    research = {"sources": [{"title": "Tiananmen Gate", "url": "https://example.test", "snippet": "five arched gateways, xumizuo, double-eaved xieshan roof, yellow glazed tiles, dougong, lattice windows"}]}

    package = build_prompt_quality_package("生成天安门城楼外观", research, brief, modeling_standard("exterior_architecture"))
    contract = package["geometry_contract"]

    assert contract["target_archetype"] == "tiananmen_gate"
    assert any("red city platform" in item for item in contract["required_components"])
    assert any("five real arched gateway voids" in item for item in contract["required_components"])
    assert any("flat cube slabs" in item for item in contract["forbidden_shortcuts"])
    recipe = package["modeling_recipe"]
    assert any("two dominant masses" in item for item in recipe["component_translation"])
    assert any("five gateway openings" in item for item in recipe["component_translation"])
    assert "build_xieshan_roof" in recipe["procedural_helpers_to_write"]
    assert any("PBR-like materials" in item for item in recipe["material_translation"])


def test_prompt_package_lines_include_blender_modeling_recipe() -> None:
    brief = {
        "generation_module": "exterior_architecture",
        "scene_goal": "Tiananmen Gate exterior",
        "space_contracts": [{"space": "city platform", "openings": ["five arched gateways"]}],
        "must_have": ["double-eaved xieshan roof"],
        "relationships": [],
        "delivery_views": [],
    }
    research = {"sources": [{"title": "Tiananmen Gate", "url": "https://example.test", "snippet": "double-eaved xieshan roof, five arched gateways, yellow glazed tiles"}]}
    package = build_prompt_quality_package("生成天安门城楼外观", research, brief, modeling_standard("exterior_architecture"))
    prompt = blender_skill_prompt({**brief, "prompt_quality_package": package}, tmp_path := Path("."), [])

    assert "Blender modeling recipe component translation" in prompt
    assert "build_xieshan_roof" in prompt
    assert "Build the five gateway openings as real structural voids" in prompt


def test_tiananmen_generated_script_contract_rejects_bad_blockout(tmp_path: Path) -> None:
    script = tmp_path / "bad_tiananmen.py"
    script.write_text(
        "\n".join(
            [
                "PLATFORM_HEIGHT = 1.59",
                "roof_base = create_cube('Roof_Base')",
                "upper_roof_base = create_cube('Upper_Roof_Base')",
                "bpy.ops.mesh.primitive_uv_sphere_add()",
                "vault.name = 'Arch_Vault_0'",
                "bpy.ops.export_scene.gltf(filepath='bad.glb')",
                "for obj in bpy.data.objects:",
                "    if obj.name.startswith(\"Arch_Vault_\"): obj.select_set(True)",
                "cam_front.ortho_scale = 40.0",
            ]
        ),
        encoding="utf-8",
    )

    failures = run_scene_workflow.generated_script_contract_failures(script, {"geometry_contract": {"target_archetype": "tiananmen_gate"}})

    assert any("1.59m" in item for item in failures)
    assert any("flat cube slabs" in item for item in failures)
    assert any("cutter objects" in item for item in failures)
    assert any("too cropped" in item for item in failures)


def test_exterior_material_targets_keep_default_layers() -> None:
    brief = fallback_brief("生成现实风格地标外观", [], "exterior")
    package = build_prompt_quality_package("重点要求屋顶细节", {"sources": []}, brief, modeling_standard("exterior_architecture"))
    assert package["material_targets"] == ["stone", "timber", "roof_tile", "metal"]


def test_auto_build_offline_stops_at_model_call_boundary(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(run_scene_workflow, "RUNS", tmp_path)
    case_dir = run_scene_workflow.run("生成一个还没有沉淀方案的地标外观", "case", offline=True, module="exterior", auto_build=True)
    manifest = json.loads((case_dir / "workflow_manifest.json").read_text(encoding="utf-8"))
    statuses = {item["name"]: item["status"] for item in manifest["stages"]}
    assert statuses["production_modeling_standard"] == "applied"
    assert statuses["scene_brief"] == "failed"
    assert "blender_code_generation" not in statuses
    assert "blender_generation" not in statuses


def test_auto_build_generates_blender_file_and_runs(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(run_scene_workflow, "RUNS", tmp_path)
    monkeypatch.setattr(run_scene_workflow, "collect_agent_reach", lambda question: {"sources": [{"title": "landmark facade", "url": "https://example.test", "snippet": "glazed roof tiles, marble stairs, red columns, lattice windows and stone plinth"}]})
    monkeypatch.setattr(
        run_scene_workflow,
        "call_model",
        lambda prompt: {"raw": {}, "brief": fallback_brief("生成现实风格地标外观", [], "exterior")},
    )
    monkeypatch.setattr(
        run_scene_workflow,
        "call_text_model",
        lambda prompt, system: {"raw": {}, "content": "```python\nprint('generated blender scene')\n```"},
    )
    monkeypatch.setattr(run_scene_workflow, "resolve_blender", lambda path=None: Path("blender.exe"))

    def fake_run_process(command: list[str], timeout: int) -> dict[str, object]:
        if "--output" in command:
            output = Path(command[command.index("--output") + 1])
            output.mkdir(parents=True, exist_ok=True)
            (output / "generated.glb").write_bytes(b"glb")
            (output / "scene_audit.json").write_text(json.dumps({"quality_checklist": {"shape": "pass"}}), encoding="utf-8")
        return {"command": command, "returncode": 0, "stdout_tail": "", "stderr_tail": ""}

    monkeypatch.setattr(run_scene_workflow, "run_process", fake_run_process)
    case_dir = run_scene_workflow.run("生成现实风格地标外观", "case", offline=False, module="exterior")
    manifest = json.loads((case_dir / "workflow_manifest.json").read_text(encoding="utf-8"))
    statuses = {item["name"]: item["status"] for item in manifest["stages"]}
    assert statuses["blender_code_generation"] == "complete"
    assert statuses["blender_generation"] == "complete"
    assert statuses["glb_validation"] == "complete"
    assert (case_dir / "generated_blender_scene.py").read_text(encoding="utf-8") == "print('generated blender scene')\n"


def test_auto_build_records_code_generation_failure(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(run_scene_workflow, "RUNS", tmp_path)
    monkeypatch.setattr(run_scene_workflow, "collect_agent_reach", lambda question: {"sources": [{"title": "landmark facade", "url": "https://example.test", "snippet": "glazed roof tiles, marble stairs, red columns, lattice windows and stone plinth"}]})
    monkeypatch.setattr(
        run_scene_workflow,
        "call_model",
        lambda prompt: {"raw": {}, "brief": fallback_brief("生成现实风格地标外观", [], "exterior")},
    )

    def fail_code_generation(prompt: str, system: str) -> dict[str, object]:
        raise RuntimeError("model unavailable")

    monkeypatch.setattr(run_scene_workflow, "call_text_model", fail_code_generation)
    case_dir = run_scene_workflow.run("生成现实风格地标外观", "case", offline=False, module="exterior")
    manifest = json.loads((case_dir / "workflow_manifest.json").read_text(encoding="utf-8"))
    statuses = {item["name"]: item["status"] for item in manifest["stages"]}
    assert statuses["blender_code_generation"] == "failed"
    assert statuses["blender_generation"] == "model_required"


def test_code_generation_retries_after_contract_failure(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(run_scene_workflow, "RUNS", tmp_path)
    monkeypatch.setattr(run_scene_workflow, "collect_agent_reach", lambda question: {"sources": [{"title": "Tiananmen Gate", "url": "https://example.test", "snippet": "five arched gateways, xumizuo, double-eaved xieshan roof, yellow glazed tiles, dougong, lattice windows"}]})
    monkeypatch.setattr(
        run_scene_workflow,
        "call_model",
        lambda prompt: {
            "raw": {},
            "brief": {
                "generation_module": "exterior_architecture",
                "scene_goal": "Tiananmen Gate exterior",
                "space_contracts": [{"space": "city platform", "vertical_geometry": ["1.59m white marble xumizuo base"], "openings": ["five arched gateways"]}],
                "must_have": ["double-eaved xieshan roof", "five arched gateways"],
                "relationships": [],
                "visual_language": {"materials": ["yellow glazed tiles", "vermilion wood"]},
                "delivery_views": [],
            },
        },
    )
    calls = {"count": 0}

    def fake_code_model(prompt: str, system: str) -> dict[str, object]:
        calls["count"] += 1
        if calls["count"] == 1:
            return {"raw": {}, "content": "PLATFORM_HEIGHT = 1.59\nroof_base = create_cube('Roof_Base')\nupper_roof_base = create_cube('Upper_Roof_Base')\ncam_front.ortho_scale = 40.0"}
        assert "Previous generated Blender script failed" in prompt
        return {"raw": {}, "content": "PLATFORM_HEIGHT = 13.0\ncam_front.ortho_scale = 90.0"}

    monkeypatch.setattr(run_scene_workflow, "call_text_model", fake_code_model)
    monkeypatch.setattr(run_scene_workflow, "resolve_blender", lambda path=None: Path("blender.exe"))

    def fake_run_process(command: list[str], timeout: int) -> dict[str, object]:
        if "--output" in command:
            output = Path(command[command.index("--output") + 1])
            output.mkdir(parents=True, exist_ok=True)
            (output / "generated.glb").write_bytes(b"glb")
            (output / "scene_audit.json").write_text(json.dumps({"quality_checklist": {"shape": "pass"}}), encoding="utf-8")
        return {"command": command, "returncode": 0, "stdout_tail": "", "stderr_tail": ""}

    monkeypatch.setattr(run_scene_workflow, "run_process", fake_run_process)
    case_dir = run_scene_workflow.run("生成天安门城楼外观", "case", offline=False, module="exterior")
    manifest = json.loads((case_dir / "workflow_manifest.json").read_text(encoding="utf-8"))
    code_stage = next(item for item in manifest["stages"] if item["name"] == "blender_code_generation")

    assert calls["count"] == 2
    assert code_stage["status"] == "complete"
    assert code_stage["attempts"] == 2


def test_blender_runtime_failure_repairs_generated_script(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(run_scene_workflow, "RUNS", tmp_path)
    monkeypatch.setattr(run_scene_workflow, "collect_agent_reach", lambda question: {"sources": [{"title": "landmark", "url": "https://example.test", "snippet": "glazed roof tiles, marble stairs, red columns, lattice windows and stone plinth"}]})
    monkeypatch.setattr(
        run_scene_workflow,
        "call_model",
        lambda prompt: {"raw": {}, "brief": fallback_brief("生成现实风格地标外观", [], "exterior")},
    )
    model_calls = {"count": 0}

    def fake_text_model(prompt: str, system: str) -> dict[str, object]:
        model_calls["count"] += 1
        if "failed when executed in Blender" in prompt:
            assert "ValueError: 1-2 args execution context is supported" in prompt
            return {"raw": {}, "content": "print('repaired blender scene')"}
        return {"raw": {}, "content": "print('broken blender scene')"}

    monkeypatch.setattr(run_scene_workflow, "call_text_model", fake_text_model)
    monkeypatch.setattr(run_scene_workflow, "resolve_blender", lambda path=None: Path("blender.exe"))
    run_attempts = {"count": 0}

    def fake_run_process(command: list[str], timeout: int) -> dict[str, object]:
        run_attempts["count"] += 1
        output = Path(command[command.index("--output") + 1])
        output.mkdir(parents=True, exist_ok=True)
        if run_attempts["count"] == 1:
            return {"command": command, "returncode": 0, "stdout_tail": "", "stderr_tail": "ValueError: 1-2 args execution context is supported"}
        (output / "generated.glb").write_bytes(b"glb")
        (output / "scene_audit.json").write_text(json.dumps({"quality_checklist": {"shape": "pass"}}), encoding="utf-8")
        return {"command": command, "returncode": 0, "stdout_tail": "", "stderr_tail": ""}

    monkeypatch.setattr(run_scene_workflow, "run_process", fake_run_process)
    case_dir = run_scene_workflow.run("生成现实风格地标外观", "case", offline=False, module="exterior")
    manifest = json.loads((case_dir / "workflow_manifest.json").read_text(encoding="utf-8"))
    generation_stage = next(item for item in manifest["stages"] if item["name"] == "blender_generation")

    assert run_attempts["count"] == 3
    assert model_calls["count"] == 2
    assert generation_stage["status"] == "complete"
    assert generation_stage["attempts"] == 2
    assert (case_dir / "generated_blender_scene.py").read_text(encoding="utf-8") == "print('repaired blender scene')\n"


def test_model_synthesis_failure_stops_without_fallback_prompt(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(run_scene_workflow, "RUNS", tmp_path)
    monkeypatch.setattr(run_scene_workflow, "collect_agent_reach", lambda question: {"sources": [{"title": "roof source", "url": "https://example.test", "snippet": "glazed roof tiles and stone plinth"}]})

    def fail_model(prompt: str) -> dict[str, object]:
        raise RuntimeError("model unavailable")

    monkeypatch.setattr(run_scene_workflow, "call_model", fail_model)
    case_dir = run_scene_workflow.run("生成现实风格地标外观", "case", offline=False, module="exterior")
    manifest = json.loads((case_dir / "workflow_manifest.json").read_text(encoding="utf-8"))
    statuses = {item["name"]: item["status"] for item in manifest["stages"]}
    assert statuses["scene_brief"] == "failed"
    assert "research_to_prompt" not in statuses
    assert not (case_dir / "skill_prompt.md").exists()


def test_prompt_package_without_exterior_features_stops_generation(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(run_scene_workflow, "RUNS", tmp_path)
    monkeypatch.setattr(run_scene_workflow, "collect_agent_reach", lambda question: {"sources": [{"title": "generic article", "url": "https://example.test", "snippet": "general travel information"}]})
    monkeypatch.setattr(
        run_scene_workflow,
        "call_model",
        lambda prompt: {"raw": {}, "brief": fallback_brief("生成现实风格地标外观", [], "exterior")},
    )
    case_dir = run_scene_workflow.run("生成现实风格地标外观", "case", offline=False, module="exterior")
    manifest = json.loads((case_dir / "workflow_manifest.json").read_text(encoding="utf-8"))
    statuses = {item["name"]: item["status"] for item in manifest["stages"]}
    assert statuses["research_to_prompt"] == "failed"
    assert "blender_skill_prompt" not in statuses
    assert not (case_dir / "skill_prompt.md").exists()


def test_blender_traceback_counts_as_failed_process() -> None:
    assert not run_scene_workflow.process_ok({"returncode": 0, "stderr_tail": "Traceback (most recent call last):"})


def test_scene_audit_failures_block_semantic_fail(tmp_path: Path) -> None:
    output = tmp_path / "model_output"
    output.mkdir()
    (output / "scene_audit.json").write_text(json.dumps({"quality_checklist": {"overview_detachment": "fail"}}), encoding="utf-8")
    assert run_scene_workflow.scene_audit_failures(output) == ["overview_detachment"]


def test_scene_audit_missing_is_failure(tmp_path: Path) -> None:
    assert run_scene_workflow.scene_audit_failures(tmp_path) == ["scene_audit.json missing"]


def test_workflow_server_infers_generated_artifacts(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(workflow_server, "ROOT", tmp_path)
    monkeypatch.setattr(workflow_server, "RUNS", tmp_path / "runs")
    case_dir = tmp_path / "runs" / "case"
    (case_dir / "model_output").mkdir(parents=True)
    (case_dir / "research.json").write_text("{}", encoding="utf-8")
    (case_dir / "skill_prompt.md").write_text("prompt", encoding="utf-8")
    (case_dir / "generated_blender_scene.py").write_text("print('ok')", encoding="utf-8")
    (case_dir / "model_output" / "model.glb").write_bytes(b"glb")
    (case_dir / "glb_validation.json").write_text("{}", encoding="utf-8")

    progress = {item["name"]: item["status"] for item in workflow_server.infer_progress(case_dir)}
    artifacts = workflow_server.artifacts(case_dir, "case")

    assert progress["Blender 生成模型"] == "complete"
    assert progress["GLB 模型校验"] == "complete"
    assert artifacts["glb"] == "runs/case/model_output/model.glb"
    assert artifacts["showcase_url"].startswith("model_showcase.html?")


def test_job_payload_treats_existing_glb_and_validation_as_complete(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(workflow_server, "ROOT", tmp_path)
    monkeypatch.setattr(workflow_server, "RUNS", tmp_path / "runs")
    case_dir = tmp_path / "runs" / "case"
    (case_dir / "model_output").mkdir(parents=True)
    (case_dir / "model_output" / "model.glb").write_bytes(b"glb")
    (case_dir / "glb_validation.json").write_text("{}", encoding="utf-8")
    job = {"id": "job", "case_id": "case", "question": "q", "module": "exterior", "status": "failed", "started_at": 1, "error": "old failure"}

    payload = workflow_server.job_payload(job)

    assert payload["status"] == "complete"
    assert payload["error"] is None


def test_job_payload_keeps_manifest_failure_even_with_artifacts(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(workflow_server, "ROOT", tmp_path)
    monkeypatch.setattr(workflow_server, "RUNS", tmp_path / "runs")
    case_dir = tmp_path / "runs" / "case"
    (case_dir / "model_output").mkdir(parents=True)
    (case_dir / "model_output" / "model.glb").write_bytes(b"glb")
    (case_dir / "glb_validation.json").write_text("{}", encoding="utf-8")
    (case_dir / "workflow_manifest.json").write_text(json.dumps({"stages": [{"name": "blender_generation", "status": "failed"}]}), encoding="utf-8")
    job = {"id": "job", "case_id": "case", "question": "q", "module": "exterior", "status": "failed", "started_at": 1, "error": "semantic failure"}

    payload = workflow_server.job_payload(job)

    assert payload["status"] == "failed"
    assert payload["error"] == "semantic failure"


def test_research_progress_requires_actual_evidence(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(workflow_server, "ROOT", tmp_path)
    monkeypatch.setattr(workflow_server, "RUNS", tmp_path / "runs")
    case_dir = tmp_path / "runs" / "case"
    case_dir.mkdir(parents=True)
    (case_dir / "research.json").write_text(json.dumps({"sources": [], "pages": []}), encoding="utf-8")
    assert not workflow_server.research_has_evidence(case_dir)

    (case_dir / "research.json").write_text(json.dumps({"sources": [{"url": "https://example.test"}], "pages": []}), encoding="utf-8")
    assert workflow_server.research_has_evidence(case_dir)


def test_archive_case_dir_moves_stale_run_before_new_job(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(workflow_server, "RUNS", tmp_path / "runs")
    case_dir = workflow_server.RUNS / "case"
    case_dir.mkdir(parents=True)
    (case_dir / "research.json").write_text(json.dumps({"sources": [{"url": "https://old.test"}]}), encoding="utf-8")

    workflow_server.archive_case_dir("case")

    assert not case_dir.exists()
    archived = list((workflow_server.RUNS / "_archive").glob("case_*"))
    assert len(archived) == 1
    assert (archived[0] / "research.json").exists()


def test_decode_image_data_url_rejects_non_image_payload() -> None:
    try:
        workflow_server.decode_image_data_url("data:text/plain;base64,SGVsbG8=")
    except ValueError as exc:
        assert "PNG" in str(exc)
    else:
        raise AssertionError("non-image data URL should be rejected")


def test_save_lattice_case_writes_analysis_package(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(workflow_server, "ROOT", tmp_path)
    monkeypatch.setattr(workflow_server, "RUNS", tmp_path / "runs")
    one_pixel_png = base64.b64encode(
        bytes.fromhex("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d49444154789c63606060f80f0001040100b51c0c020000000049454e44ae426082")
    ).decode("ascii")
    image = f"data:image/png;base64,{one_pixel_png}"
    payload = {
        "case_id": "lattice_test",
        "title": "test lattice",
        "source_url": "https://example.test/lattice",
        "original_filename": "test.png",
        "schema": {
            "frame": {"width_mm": 1500, "height_mm": 1800},
            "nodes": [{"id": "N001"}, {"id": "N002"}],
            "edges": [{"id": "E001", "start": "N001", "end": "N002"}],
            "confidence": 0.8,
            "estimated_fields": ["bars.depth_mm"],
        },
        "images": {name: image for name in ("original", "rectified", "mask", "skeleton", "overlay")},
    }

    result = workflow_server.save_lattice_case(payload)
    case_dir = tmp_path / "runs" / "lattice_test"

    assert result["status"] == "complete"
    assert (case_dir / "source" / "original.png").exists()
    assert (case_dir / "analysis" / "lattice_schema.json").exists()
    assert (case_dir / "analysis" / "graph_overlay.png").exists()
    report = json.loads((case_dir / "analysis" / "analysis_report.json").read_text(encoding="utf-8"))
    assert report["node_count"] == 2
    assert report["edge_count"] == 1
    manifest = json.loads((case_dir / "workflow_manifest.json").read_text(encoding="utf-8"))
    assert manifest["stages"][4]["status"] == "complete"
    assert manifest["stages"][5]["status"] == "pending"


def test_fetch_page_uses_jina_reader_after_direct_failure(monkeypatch) -> None:
    attempts = {"jina": 0}

    class FakeResponse:
        headers = {"Content-Type": "text/plain"}

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def read(self, limit):
            return b"Title: Tiananmen\n\nusable page content"

    def fake_urlopen(request, timeout=0):
        if "r.jina.ai" in request.full_url:
            attempts["jina"] += 1
            if attempts["jina"] == 1:
                raise RuntimeError("Remote end closed connection without response")
            return FakeResponse()
        raise RuntimeError("HTTP Error 403: Forbidden")

    monkeypatch.setattr(agent_reach_channels, "urlopen", fake_urlopen)
    page = agent_reach_channels.fetch_page("https://baike.baidu.com/item/test")
    assert page["status"] == "passed"
    assert page["reader"] == "jina_reader"
    assert "usable page content" in page["text"]
    assert attempts["jina"] == 2


def test_blender_script_prompt_requires_signature_feature_audit() -> None:
    from scene_workflow.blender_script_generation import blender_script_prompt

    prompt = blender_script_prompt("RESEARCH TO MODEL PROMPT PACKAGE:\n- signature feature rules: roof cannot be a single flat slab")
    assert "Convert every signature feature rule into real geometry" in prompt
    assert "quality_checklist" in prompt
    assert "never call bpy.ops.wm.append/link with empty filepath" in prompt


def test_sanitize_blender_code_removes_empty_append_calls() -> None:
    from scene_workflow.blender_script_generation import sanitize_blender_code

    code = sanitize_blender_code(
        "\n".join(
            [
                "bpy.ops.wm.append(filepath=\"\", directory=\"\", filename=\"\")",
                "bpy.ops.object.select_all(action='SELECT')",
                "bpy.ops.wm.link(filepath='', directory='', filename='')",
            ]
        )
    )
    assert "wm.append" not in code
    assert "wm.link" not in code
    assert "select_all" in code


def test_sanitize_blender_code_removes_dummy_append_calls() -> None:
    from scene_workflow.blender_script_generation import sanitize_blender_code

    code = sanitize_blender_code(
        "\n".join(
            [
                "bpy.ops.wm.append(filepath=\"//\")  # Dummy to avoid error",
                "bpy.ops.wm.link(filepath='//asset.blend')",
                "bpy.ops.object.select_all(action='SELECT')",
            ]
        )
    )

    assert "wm.append" not in code
    assert "wm.link" not in code
    assert "select_all" in code


def test_sanitize_blender_code_removes_multiline_append_calls() -> None:
    from scene_workflow.blender_script_generation import sanitize_blender_code

    code = sanitize_blender_code(
        "\n".join(
            [
                "blend_path = 'model.blend'",
                "bpy.ops.wm.append(",
                "    filepath='//',",
                "    directory=os.path.dirname(bpy.data.filepath) + '/',",
                "    filename=''",
                ")",
                "bpy.ops.wm.save_mainfile(filepath=blend_path)",
            ]
        )
    )

    assert "wm.append" not in code
    assert "directory=os.path.dirname" not in code
    assert "save_mainfile" in code


def test_sanitize_blender_code_removes_collection_parent_assignments() -> None:
    from scene_workflow.blender_script_generation import sanitize_blender_code

    code = sanitize_blender_code(
        "\n".join(
            [
                "xumizuo.parent = geo_coll",
                "cam_obj.parent = cam_coll",
                "roof.parent = roof_parent_obj",
            ]
        )
    )

    assert "xumizuo.parent = geo_coll" not in code
    assert "cam_obj.parent = cam_coll" not in code
    assert "roof.parent = roof_parent_obj" in code


def test_sanitize_blender_code_rewrites_legacy_join_context() -> None:
    from scene_workflow.blender_script_generation import sanitize_blender_code

    code = sanitize_blender_code(
        "\n".join(
            [
                "def join_objects(objects, name):",
                "    ctx = bpy.context.copy()",
                "    ctx['active_object'] = objects[0]",
                "    ctx['selected_editable_objects'] = objects",
                "    bpy.ops.object.join(ctx)",
                "    return objects[0]",
            ]
        )
    )
    assert "bpy.ops.object.join(ctx)" not in code
    assert "bpy.ops.object.join()" in code
    assert "obj.select_set(True)" in code


def test_sanitize_blender_code_rewrites_reordered_legacy_join_context() -> None:
    from scene_workflow.blender_script_generation import sanitize_blender_code

    code = sanitize_blender_code(
        "\n".join(
            [
                "def join_objects(objects):",
                "    ctx = bpy.context.copy()",
                "    ctx['selected_editable_objects'] = objects",
                "    ctx['active_object'] = objects[0]",
                "    bpy.ops.object.join(ctx)",
                "    return objects[0]",
            ]
        )
    )
    assert "bpy.ops.object.join(ctx)" not in code
    assert "bpy.ops.object.join()" in code
    assert "obj.select_set(True)" in code


def test_generated_script_contract_rejects_blender_api_hazards(tmp_path: Path) -> None:
    script = tmp_path / "bad_api.py"
    script.write_text(
        "\n".join(
            [
                "bpy.ops.object.join(ctx)",
                "bpy.ops.wm.append(filepath='//')",
            ]
        ),
        encoding="utf-8",
    )

    failures = run_scene_workflow.generated_script_contract_failures(script, {"geometry_contract": {"target_archetype": "generic_exterior_landmark"}})

    assert any("join(ctx)" in item for item in failures)
    assert any("append/link" in item for item in failures)


def test_sanitize_blender_code_selects_curve_before_mesh_ops() -> None:
    from scene_workflow.blender_script_generation import sanitize_blender_code

    code = sanitize_blender_code(
        "\n".join(
            [
                "def create_curve(curve_obj):",
                "    # Convert to mesh",
                "    bpy.context.view_layer.objects.active = curve_obj",
                "    bpy.ops.object.convert(target='MESH')",
                "    ",
                "    # Extrude",
                "    bpy.ops.object.mode_set(mode='EDIT')",
            ]
        )
    )
    assert "curve_obj.select_set(True)" in code
    assert "curve_obj = bpy.context.view_layer.objects.active" in code


def test_sanitize_blender_code_finds_principled_bsdf_by_type() -> None:
    from scene_workflow.blender_script_generation import sanitize_blender_code

    code = sanitize_blender_code('bsdf = mat.node_tree.nodes["Principled BSDF"]')
    assert 'nodes["Principled BSDF"]' not in code
    assert "BSDF_PRINCIPLED" in code


def test_sanitize_blender_code_uses_blender_5_noise_node_id() -> None:
    from scene_workflow.blender_script_generation import sanitize_blender_code

    code = sanitize_blender_code("noise_tex = mat.node_tree.nodes.new('ShaderNodeNoiseTexture')")
    assert "ShaderNodeNoiseTexture" not in code
    assert "ShaderNodeTexNoise" in code


def test_sanitize_blender_code_removes_obsolete_gltf_export_colors() -> None:
    from scene_workflow.blender_script_generation import sanitize_blender_code

    code = sanitize_blender_code("bpy.ops.export_scene.gltf(\n    export_colors=True,\n    export_materials='EXPORT',\n)")
    assert "export_colors" not in code
    assert "export_materials" in code


def test_baike_terms_remove_task_words() -> None:
    terms = _baike_terms("生成故宫角楼外观，现实风格，重点表现黄色琉璃瓦和斗拱")
    assert terms
    assert all("生成" not in item and "外观" not in item for item in terms)

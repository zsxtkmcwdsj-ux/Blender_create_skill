from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from scene_workflow.agent_reach_channels import collect_agent_reach
from scene_workflow.blender_script_generation import blender_script_prompt, extract_python_code, sanitize_blender_code
from scene_workflow.production_modeling_standard import modeling_standard
from scene_workflow.research_to_prompt import build_prompt_quality_package
from scene_workflow.scene_brief import blender_skill_prompt, normalize_generation_module, parse_json, synthesis_prompt


ROOT = Path(__file__).resolve().parent
RUNS = ROOT / "runs"
DEFAULT_BLENDER = Path(r"E:\app\Game_1234\Blender_001\blender.exe")
VALIDATE_GLB = ROOT / "blender-mcp-reference-modeling" / "scripts" / "validate_glb.py"


def load_env() -> None:
    path = ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def call_text_model(prompt: str, system: str) -> dict[str, Any]:
    api_key = os.getenv("DASHSCOPE_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("DASHSCOPE_API_KEY is not configured")
    endpoint = os.getenv("DASHSCOPE_GENERATION_URL", "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation")
    body = {
        "model": os.getenv("QWEN_MODEL", "qwen-plus"),
        "input": {"messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}]},
        "parameters": {"temperature": 0.2, "max_tokens": int(os.getenv("QWEN_MAX_TOKENS", "8000")), "result_format": "message"},
    }
    request = urllib.request.Request(endpoint, data=json.dumps(body, ensure_ascii=False).encode("utf-8"), headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=240) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"model HTTP {exc.code}: {detail or exc.reason}") from exc
    content = payload["output"]["choices"][0]["message"]["content"]
    return {"raw": payload, "content": content}


def call_model(prompt: str) -> dict[str, Any]:
    result = call_text_model(prompt, "你是建筑空间概念简报编辑，只输出合法 JSON。")
    content = result["content"]
    return {"raw": result["raw"], "brief": parse_json(content)}


def resolve_blender(path: str | None = None) -> Path:
    candidate = Path(path or os.getenv("BLENDER_EXE", "") or DEFAULT_BLENDER)
    if not candidate.is_file():
        raise FileNotFoundError(f"Blender executable not found: {candidate}")
    return candidate


def run_process(command: list[str], timeout: int) -> dict[str, Any]:
    completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    return {
        "command": command,
        "returncode": completed.returncode,
        "stdout_tail": completed.stdout[-4000:],
        "stderr_tail": completed.stderr[-4000:],
    }


def process_ok(result: dict[str, Any]) -> bool:
    stderr = str(result.get("stderr_tail", ""))
    return result.get("returncode") == 0 and "Traceback (most recent call last)" not in stderr


def stage(name: str, status: str, **extra: Any) -> dict[str, Any]:
    return {"name": name, "status": status, **extra}


def write_manifest(case_dir: Path, question: str, generation_module: str, stages: list[dict[str, Any]]) -> None:
    manifest = {
        "question": question,
        "generation_module": generation_module,
        "case_dir": str(case_dir),
        "actual_flow": "text -> research package -> research-to-prompt package -> production modeling standard -> scene brief -> Blender skill prompt -> generated Blender code -> Blender generation -> GLB validation",
        "stages": stages,
    }
    (case_dir / "workflow_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def research_has_evidence(research: dict[str, Any]) -> bool:
    sources = research.get("sources", [])
    pages = research.get("pages", [])
    return bool(sources) or any(item.get("status") == "passed" and item.get("text") for item in pages)


def prompt_package_failures(package: dict[str, Any], module: str) -> list[str]:
    failures: list[str] = []
    if not package.get("evidence_for_prompt"):
        failures.append("no research evidence was converted into the Blender prompt package")
    if module == "exterior_architecture" and not package.get("signature_feature_rules"):
        failures.append("no exterior signature feature rules were produced")
    if not package.get("detail_targets"):
        failures.append("detail targets are missing")
    if not package.get("material_targets"):
        failures.append("material targets are missing")
    contract = package.get("geometry_contract", {})
    if module == "exterior_architecture" and not contract.get("required_components"):
        failures.append("geometry contract has no required exterior components")
    recipe = package.get("modeling_recipe", {})
    if not recipe.get("component_translation") or not recipe.get("procedural_helpers_to_write"):
        failures.append("Blender modeling recipe is missing component translation or procedural helper guidance")
    return failures


def generated_script_contract_failures(script_path: Path, package: dict[str, Any]) -> list[str]:
    if not script_path.exists():
        return [f"generated Blender script missing: {script_path}"]
    text = script_path.read_text(encoding="utf-8", errors="replace")
    lower = text.lower()
    contract = package.get("geometry_contract", {})
    failures: list[str] = []
    if contract.get("target_archetype") == "tiananmen_gate":
        if re.search(r"\bPLATFORM_HEIGHT\s*=\s*1\.59\b", text):
            failures.append("Tiananmen city platform uses the 1.59m xumizuo height as the whole platform")
        if re.search(r"\broof_base\s*=\s*create_cube", lower) and re.search(r"\bupper_roof_base\s*=\s*create_cube", lower):
            failures.append("double-eaved xieshan roof is modeled as flat cube slabs")
        export_at = lower.find("export_scene.gltf")
        arch_cleanup_at = lower.find("startswith(\"arch_vault_", export_at)
        if "arch_vault_" in lower and export_at >= 0 and (arch_cleanup_at < 0 or arch_cleanup_at > export_at):
            failures.append("archway Boolean cutter objects may be exported before cleanup")
        scale_match = re.search(r"\bcam_front\.ortho_scale\s*=\s*([0-9.]+)", text)
        if scale_match and float(scale_match.group(1)) < 70:
            failures.append("front overview camera is too cropped for the full Tiananmen platform")
    if "bpy.ops.object.join(ctx)" in text:
        failures.append("Blender 5 incompatible object join call uses positional context: bpy.ops.object.join(ctx)")
    if re.search(r"bpy\.ops\.wm\.(?:append|link)\(", text):
        failures.append("generated script tries to append/link external Blender assets without a verified asset path")
    return failures


def scene_audit_failures(output_dir: Path) -> list[str]:
    path = output_dir / "scene_audit.json"
    if not path.exists():
        return ["scene_audit.json missing"]
    try:
        audit = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"scene_audit.json invalid: {exc}"]
    checklist = audit.get("quality_checklist", {})
    failures = [str(name) for name, value in checklist.items() if str(value).lower().startswith("fail")]
    return failures


def run(
    question: str,
    case_id: str | None = None,
    references: list[str] | None = None,
    offline: bool = False,
    module: str | None = None,
    blender_script: str | None = None,
    blender_output: str | None = None,
    blender_exe: str | None = None,
    validate_glb: str | None = None,
    auto_build: bool = True,
) -> Path:
    load_env()
    generation_module = normalize_generation_module(module)
    case_dir = RUNS / (case_id or "scene_case")
    case_dir.mkdir(parents=True, exist_ok=True)
    references = references or []
    stages: list[dict[str, Any]] = [
        stage("text_request", "complete", question=question, generation_module=generation_module)
    ]
    standard = modeling_standard(generation_module)
    stages.append(stage("production_modeling_standard", "applied", items=standard))
    research = {"status": "offline", "question": question, "channels": {}, "sources": [], "pages": []} if offline else collect_agent_reach(question)
    (case_dir / "research.json").write_text(json.dumps(research, ensure_ascii=False, indent=2), encoding="utf-8")
    research_status = "complete" if offline or research_has_evidence(research) else "empty"
    stages.append(stage("research_package", research_status, file="research.json", mode="offline" if offline else "agent_reach", source_count=len(research.get("sources", [])), page_count=len(research.get("pages", []))))
    if offline:
        stages.append(stage("scene_brief", "failed", reason="offline mode disables research/model synthesis; strict workflow does not create fallback prompts"))
        write_manifest(case_dir, question, generation_module, stages)
        return case_dir
    if not offline and research_status != "complete":
        stages.append(stage("scene_brief", "failed", reason="research package has no usable evidence"))
        write_manifest(case_dir, question, generation_module, stages)
        return case_dir
    try:
        synthesis = call_model(synthesis_prompt(question, research, generation_module))
        brief = synthesis["brief"]
        brief["generation_module"] = generation_module
        (case_dir / "synthesis_raw.json").write_text(json.dumps(synthesis["raw"], ensure_ascii=False, indent=2), encoding="utf-8")
        synthesis_status = "model"
    except Exception as exc:
        stages.append(stage("scene_brief", "failed", reason=f"model synthesis failed: {exc}"))
        write_manifest(case_dir, question, generation_module, stages)
        return case_dir
    prompt_quality_package = build_prompt_quality_package(question, research, brief, standard)
    package_failures = prompt_package_failures(prompt_quality_package, generation_module)
    if package_failures:
        stages.append(stage("research_to_prompt", "failed", file="prompt_quality_package.json", reason="; ".join(package_failures)))
        (case_dir / "prompt_quality_package.json").write_text(json.dumps(prompt_quality_package, ensure_ascii=False, indent=2), encoding="utf-8")
        write_manifest(case_dir, question, generation_module, stages)
        return case_dir
    brief["prompt_quality_package"] = prompt_quality_package
    (case_dir / "prompt_quality_package.json").write_text(json.dumps(prompt_quality_package, ensure_ascii=False, indent=2), encoding="utf-8")
    (case_dir / "scene_brief.json").write_text(json.dumps(brief, ensure_ascii=False, indent=2), encoding="utf-8")
    skill_prompt_text = blender_skill_prompt(brief, case_dir, references)
    (case_dir / "skill_prompt.md").write_text(skill_prompt_text, encoding="utf-8")
    stages.append(stage("research_to_prompt", "complete", file="prompt_quality_package.json", detail_targets=len(prompt_quality_package["detail_targets"]), signature_features=len(prompt_quality_package["signature_feature_rules"]), material_targets=len(prompt_quality_package["material_targets"])))
    stages.append(stage("scene_brief", "complete", file="scene_brief.json", synthesis=synthesis_status))
    stages.append(stage("blender_skill_prompt", "complete", file="skill_prompt.md"))
    handoff = {
        "question": question,
        "synthesis_status": synthesis_status,
        "generation_module": generation_module,
        "workflow_mode": brief.get("envelope_model", "continuous_shell_with_explicit_openings"),
        "research_file": "research.json",
        "brief_file": "scene_brief.json",
        "prompt_quality_package_file": "prompt_quality_package.json",
        "skill_prompt_file": "skill_prompt.md",
        "space_contract_reference": "blender-mcp-reference-modeling/references/spatial-grammar.md",
        "hard_finish_contract_reference": "blender-mcp-reference-modeling/references/closed-space-hard-finish.md",
        "references": references,
    }
    (case_dir / "handoff.json").write_text(json.dumps(handoff, ensure_ascii=False, indent=2), encoding="utf-8")
    stages.append(stage("handoff_package", "complete", file="handoff.json"))

    model_output = Path(blender_output).resolve() if blender_output else case_dir / "model_output"
    glb_path = Path(validate_glb).resolve() if validate_glb else None
    generated_by_workflow = False
    if auto_build and not blender_script:
        generated_script = case_dir / "generated_blender_scene.py"
        if offline:
            stages.append(stage("blender_code_generation", "model_required", reason="offline mode disables automatic Blender code generation"))
        else:
            try:
                code_prompt = blender_script_prompt(skill_prompt_text)
                contract_failures: list[str] = []
                for attempt in range(1, 3):
                    code_result = call_text_model(code_prompt, "You write production Blender Python scripts. Return code only.")
                    code = sanitize_blender_code(extract_python_code(code_result["content"]))
                    generated_script.write_text(code, encoding="utf-8")
                    (case_dir / "generated_blender_scene_raw.json").write_text(json.dumps(code_result["raw"], ensure_ascii=False, indent=2), encoding="utf-8")
                    contract_failures = generated_script_contract_failures(generated_script, prompt_quality_package)
                    if not contract_failures:
                        blender_script = str(generated_script)
                        generated_by_workflow = True
                        stages.append(stage("blender_code_generation", "complete", file="generated_blender_scene.py", attempts=attempt, source="model_generated"))
                        break
                    code_prompt = blender_script_prompt(skill_prompt_text) + "\n\nPrevious generated Blender script failed these hard geometry checks:\n- " + "\n- ".join(contract_failures) + "\nRewrite the full script. Do not patch around the checker; change the actual modeling strategy."
                if not blender_script:
                    stages.append(stage("blender_code_generation", "failed", file="generated_blender_scene.py", attempts=2, reason="; ".join(contract_failures)))
            except Exception as exc:
                stages.append(stage("blender_code_generation", "failed", reason=str(exc)))

    if blender_script:
        blender = resolve_blender(blender_exe)
        script = Path(blender_script).resolve()
        if not script.is_file():
            raise FileNotFoundError(f"Blender script not found: {script}")
        model_output.mkdir(parents=True, exist_ok=True)
        result: dict[str, Any] = {}
        failures: list[str] = []
        generation_ok = False
        max_attempts = 2 if generated_by_workflow else 1
        for attempt in range(1, max_attempts + 1):
            result = run_process([str(blender), "--background", "--python", str(script), "--", "--output", str(model_output)], timeout=3600)
            failures = scene_audit_failures(model_output) if process_ok(result) else []
            generation_ok = process_ok(result) and not failures
            if generation_ok or not generated_by_workflow or attempt == max_attempts:
                break
            repair_prompt = (
                "The Blender Python script below failed when executed in Blender. "
                "Rewrite the full script, preserving the modeling brief and all deliverables. "
                "Fix the actual Blender API/runtime error; do not remove required geometry, renders, exports, or scene_audit.json.\n\n"
                f"Blender stderr tail:\n{result.get('stderr_tail', '')}\n\n"
                f"Blender stdout tail:\n{result.get('stdout_tail', '')}\n\n"
                f"Modeling brief:\n{skill_prompt_text}\n\n"
                f"Current script:\n```python\n{script.read_text(encoding='utf-8', errors='replace')}\n```"
            )
            repaired = call_text_model(repair_prompt, "You repair Blender 5 Python scripts. Return full Python code only.")
            script.write_text(sanitize_blender_code(extract_python_code(repaired["content"])), encoding="utf-8")
        stages.append(stage("blender_generation", "complete" if generation_ok else "failed", script=str(script), output_dir=str(model_output), result=result, semantic_failures=failures, attempts=max_attempts if generated_by_workflow else 1))
        if generation_ok and not glb_path:
            glbs = sorted(model_output.glob("*.glb"))
            if len(glbs) == 1:
                glb_path = glbs[0]
    elif auto_build:
        stages.append(stage("blender_generation", "model_required", reason="automatic Blender code was not produced"))
    else:
        stages.append(stage("blender_generation", "prompt_only", reason="automatic Blender generation disabled"))

    if glb_path:
        blender = resolve_blender(blender_exe)
        report = case_dir / "glb_validation.json"
        result = run_process([str(blender), "--background", "--python", str(VALIDATE_GLB), "--", "--glb", str(glb_path), "--output", str(report)], timeout=900)
        stages.append(stage("glb_validation", "complete" if process_ok(result) else "failed", glb=str(glb_path), report=str(report), result=result))
    else:
        stages.append(stage("glb_validation", "pending", reason="no GLB path was provided or auto-detected"))

    write_manifest(case_dir, question, generation_module, stages)
    return case_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Agent-reach research to Blender skill handoff")
    parser.add_argument("--question", required=True)
    parser.add_argument("--case-id", default="scene_case")
    parser.add_argument("--reference", action="append", default=[])
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--module", choices=["interior", "exterior", "interior_space", "exterior_architecture", "室内", "室外", "外观"], default="interior")
    parser.add_argument("--blender-script", help="Debug override: run this Blender Python file instead of generated code")
    parser.add_argument("--blender-output", help="Output directory passed to --blender-script; defaults to runs/<case_id>/model_output")
    parser.add_argument("--blender-exe", help="Blender executable; defaults to BLENDER_EXE or the configured local Blender path")
    parser.add_argument("--validate-glb", help="Optional GLB path to validate after handoff or generation")
    parser.add_argument("--prompt-only", action="store_true", help="Stop after writing the modeling prompt and package files")
    args = parser.parse_args()
    print(run(args.question, args.case_id, args.reference, args.offline, args.module, args.blender_script, args.blender_output, args.blender_exe, args.validate_glb, not args.prompt_only))


if __name__ == "__main__":
    main()

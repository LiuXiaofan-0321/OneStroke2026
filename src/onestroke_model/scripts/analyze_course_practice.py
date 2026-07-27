from __future__ import annotations

import argparse
import json
from pathlib import Path

from onestroke_model.course_practice import CoursePracticeAnalyzer
from onestroke_model.feedback import call_openai_compatible
from onestroke_model.utils.io import write_json


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analyze one course-pack writing image with B2 and evidence-grounded feedback."
    )
    parser.add_argument("--image", required=True)
    parser.add_argument("--course-id", required=True)
    parser.add_argument("--target-char", required=True)
    parser.add_argument("--model-config", default="configs/segformer_b2_v1_delivery.yaml")
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--course-config", default="configs/course_packs.yaml")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--max-findings", type=int, default=3)
    parser.add_argument("--model-version", default="segformer-b2-v1")
    parser.add_argument(
        "--llm-url", default=None, help="Optional OpenAI-compatible /chat/completions URL."
    )
    parser.add_argument("--llm-model", default=None)
    parser.add_argument("--llm-api-key-env", default="ONESTROKE_LLM_API_KEY")
    args = parser.parse_args()
    if bool(args.llm_url) != bool(args.llm_model):
        raise SystemExit("--llm-url and --llm-model must be supplied together")
    analyzer = CoursePracticeAnalyzer.from_paths(
        model_config_path=args.model_config,
        checkpoint_path=args.checkpoint,
        course_config_path=args.course_config,
        model_version=args.model_version,
    )
    result = analyzer.analyze(
        image_path=args.image,
        course_id=args.course_id,
        target_char=args.target_char,
        output_dir=args.output_dir,
        max_findings=args.max_findings,
    )
    if args.llm_url:
        feedback_path = Path(args.output_dir) / "feedback_contract.json"
        contract = json.loads(feedback_path.read_text(encoding="utf-8"))
        rendered = call_openai_compatible(
            contract["llm_messages"],
            api_url=args.llm_url,
            model=args.llm_model,
            api_key_env=args.llm_api_key_env,
        )
        write_json(Path(args.output_dir) / "llm_feedback.json", rendered)
        result["llm_feedback_asset"] = "llm_feedback.json"
        write_json(Path(args.output_dir) / "result.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

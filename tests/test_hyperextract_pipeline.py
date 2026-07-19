import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.outputs import ChatGeneration, LLMResult

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from hyperextract_clients import UsageRecorder, llm_settings
from run_hyperextract_pipeline import (
    aggregate_graph,
    coalesce_records,
    priority_units,
    usage_summary,
    write_cost_audit,
)


def record(paper_id, chunk_id, text, section):
    return {
        "id": chunk_id,
        "text": text,
        "metadata": {"paper_id": paper_id, "page": 1, "section": section},
    }


class HyperExtractPipelineTest(unittest.TestCase):
    def test_model_strength_resolution_and_fallback(self):
        environment = {
            "OPENAI_BASE_URL": "https://example.test/v1",
            "OPENAI_API_KEY": "test-key",
            "OPENAI_STRONG_MODEL_ID": "strong-model",
            "OPENAI_MEDIUM_MODEL_ID": "medium-model",
            "OPENAI_WEAK_MODEL_ID": "",
        }
        with patch.dict("os.environ", environment, clear=True):
            self.assertEqual(llm_settings("strong").model, "strong-model")
            self.assertEqual(llm_settings("medium").model, "medium-model")
            self.assertEqual(llm_settings("weak").model, "strong-model")

    def test_units_and_priority_cap(self):
        records = [
            record("P01", "c1", "a" * 4, "Methods"),
            record("P01", "c2", "b" * 4, "Results"),
            record("P02", "c3", "c" * 4, "Introduction"),
        ]
        units = coalesce_records(records, 6)
        self.assertEqual([unit["id"] for unit in units], ["c1", "c2", "c3"])
        self.assertEqual(priority_units(units, ["method", "result"], 1), {"c1"})

    def test_two_stage_wins_deterministic_merge(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            for mode, confidence, description in (
                ("one-stage", 0.9, "first"),
                ("two-stage", 0.8, "reviewed"),
            ):
                path = base / "chunks" / mode / "unit.json"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(
                    json.dumps(
                        {
                            "mode": mode,
                            "graph": {
                                "nodes": [{"name": "n", "confidence": confidence, "description": description}],
                                "edges": [],
                            },
                        }
                    )
                )
            aggregate_graph(base, base / "knowledge-abstract", "en")
            graph = json.loads((base / "knowledge-abstract/data.json").read_text())
            self.assertEqual(graph["nodes"][0]["description"], "reviewed")

    def test_usage_summary_marks_hidden_requests(self):
        rows = [
            {"unit_id": "u1", "mode": "one-stage", "attempt": 1, "total_tokens": 100},
            {"unit_id": "u1", "mode": "one-stage", "attempt": 1, "total_tokens": 25},
            {"unit_id": "u2", "mode": "two-stage", "attempt": 1, "total_tokens": 40},
            {"unit_id": "u2", "mode": "two-stage", "attempt": 1, "total_tokens": 50},
        ]
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "usage.jsonl"
            path.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
            summary = usage_summary(path)
            self.assertEqual(summary["requests"], 4)
            self.assertEqual(summary["expected_requests"], 3)
            self.assertEqual(summary["unexpected_requests"], 1)
            self.assertEqual(summary["expected_total_tokens"], 190)
            self.assertEqual(summary["unexpected_total_tokens"], 25)

    def test_usage_recorder_saves_request_payload(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "usage.jsonl"
            recorder = UsageRecorder(path)
            recorder.set_context(unit_id="u1", paper_id="P01", mode="one-stage", attempt=1)
            recorder.on_chat_model_start({}, [[HumanMessage(content="source text")]], run_id="r1")
            recorder.on_llm_end(
                LLMResult(
                    generations=[[ChatGeneration(message=AIMessage(content="answer"))]],
                    llm_output={
                        "token_usage": {
                            "prompt_tokens": 3,
                            "completion_tokens": 2,
                            "total_tokens": 5,
                        }
                    },
                ),
                run_id="r1",
            )
            usage = json.loads(path.read_text())
            request = json.loads((Path(temporary) / usage["request_file"]).read_text())
            self.assertIn("source text", json.dumps(request["input"]))
            self.assertIn("answer", json.dumps(request["output"]))
            self.assertEqual(usage["request_index"], 1)
            self.assertEqual(usage["total_tokens"], 5)

    def test_cost_audit_separates_failed_request_projection(self):
        usage = {
            "errors": 1,
            "by_mode": {
                "one-stage": {
                    "expected_requests": 3,
                    "errors": 1,
                    "expected_input_tokens": 10,
                    "expected_output_tokens": 20,
                    "expected_total_tokens": 30,
                },
                "two-stage": {
                    "expected_requests": 2,
                    "expected_input_tokens": 5,
                    "expected_output_tokens": 10,
                    "expected_total_tokens": 15,
                },
            },
        }
        selected = [{"text": "a" * 100, "metadata": {"paper_id": "P01"}}]
        all_records = selected + [{"text": "b" * 100, "metadata": {"paper_id": "P02"}}]
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            (base / "cost-audit.json").write_text(
                json.dumps({"actual": {"elapsed_s": 5, "run_attempts": 1}})
            )
            write_cost_audit(base, usage, selected, all_records, 3)
            audit = json.loads((base / "cost-audit.json").read_text())
            self.assertEqual(audit["actual"]["elapsed_s"], 8)
            self.assertEqual(audit["actual"]["run_attempts"], 2)
            self.assertEqual(audit["projection"]["requests"], 8)
            self.assertEqual(
                audit["projection"]["observed_requests_including_failure_pattern"], 10
            )


if __name__ == "__main__":
    unittest.main()

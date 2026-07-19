import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from run_paper_memory_pipeline import (
    MemoryItem,
    PaperMemory,
    PaperConsolidation,
    MemoryReview,
    MemoryReviewBatch,
    bibliography,
    consolidate_memory,
    layout_quote_matches,
    partition_records,
    rebuild_outputs,
    review_memories,
    validate_memory,
)
from hyperextract_clients import UsageRecorder


class PaperMemoryPipelineTest(unittest.TestCase):
    def test_review_narrows_and_rejects_unsupported_memories(self):
        class FakeLLM:
            def with_structured_output(self, schema, method):
                return self

            def invoke(self, messages):
                return MemoryReviewBatch(
                    reviews=[
                        MemoryReview(
                            memory_id="P01-M001",
                            verdict="narrow",
                            revised_statement="Supported clause.",
                            subject="A",
                            relation="supports",
                            object="B",
                        ),
                        MemoryReview(memory_id="P01-M002", verdict="reject", reason="unsupported"),
                    ]
                )

        memories = [
            {
                "memory_id": "P01-M001",
                "statement": "Composite claim.",
                "source_chunk_ids": ["c1"],
                "causal_status": "none",
            },
            {
                "memory_id": "P01-M002",
                "statement": "Unsupported.",
                "source_chunk_ids": ["c1"],
                "causal_status": "none",
            },
        ]
        with tempfile.TemporaryDirectory() as temporary:
            recorder = UsageRecorder(Path(temporary) / "usage.jsonl")
            accepted, rejected = review_memories(
                FakeLLM(), recorder, "P01", memories, {"c1": {"text": "source"}}, "medium"
            )
        self.assertEqual(accepted[0]["statement"], "Supported clause.")
        self.assertEqual(accepted[0]["relation"], "supports")
        self.assertEqual(rejected[0]["review_status"], "llm-review-rejected")

    def test_bibliography_preserves_citation_metadata(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = Path(temporary)
            papers = vault / "wiki/papers"
            papers.mkdir(parents=True)
            (papers / "P01-example.md").write_text(
                """---
bibtex: |
  @article{example2026,
    title={Example},
    author={Ada Lovelace and Alan Turing},
    doi={10.1000/example}
  }
---
# Example Paper

## Basic Information
- Year/source: 2026, Example Conference.
- URL: https://example.test/paper
"""
            )
            value = bibliography(vault, "P01", "fallback")
            self.assertEqual(value["citation_key"], "example2026")
            self.assertEqual(value["doi"], "10.1000/example")
            self.assertEqual(value["authors"], ["Ada Lovelace", "Alan Turing"])
            self.assertIn("@article", value["bibtex"])

    def test_partition_and_quote_validation(self):
        records = [
            {
                "id": "P01:fulltext:1",
                "text": "alpha evidence",
                "metadata": {"paper_id": "P01"},
            },
            {
                "id": "P01:fulltext:2",
                "text": "beta evidence",
                "metadata": {"paper_id": "P01"},
            },
        ]
        self.assertEqual(len(partition_records(records, 20)), 2)
        memory = PaperMemory(
            one_sentence_summary="summary",
            study_design="design",
            memories=[
                MemoryItem(
                    kind="finding",
                    statement="Alpha was observed.",
                    importance=5,
                    evidence_quote="alpha evidence",
                    location="P01|page=1|section=Results|chunk=P01:fulltext:1",
                    subject="alpha",
                    relation="supports",
                    object="result",
                ),
                MemoryItem(
                    kind="finding",
                    statement="Unsupported statement.",
                    importance=1,
                    evidence_quote="missing quote",
                    location="P01|page=1|section=Results|chunk=P01:fulltext:2",
                ),
            ],
        )
        corpus = {record["id"]: record for record in records}
        valid, rejected = validate_memory(memory, "P01", corpus, 32)
        self.assertEqual(len(valid), 1)
        self.assertEqual(len(rejected), 1)
        self.assertEqual(valid[0]["source_chunk_ids"], ["P01:fulltext:1"])

    def test_memory_accepts_mitigation_relation(self):
        memory = MemoryItem(
            kind="mechanism",
            statement="Scaffolding mitigates unsupported answer generation.",
            importance=4,
            evidence_quote="scaffolding mitigates unsupported answer generation",
            location="P01|chunk=P01:fulltext:1",
            subject="scaffolding",
            relation="mitigates",
            object="unsupported answer generation",
        )
        self.assertEqual(memory.relation, "mitigates")

    def test_memory_accepts_study_design_kind(self):
        memory = MemoryItem(
            kind="study_design",
            statement="The study used a randomized controlled design.",
            importance=5,
            evidence_quote="randomized controlled design",
            location="P01|chunk=P01:fulltext:1",
        )
        self.assertEqual(memory.kind, "study_design")

    def test_memory_defaults_importance_and_accepts_limits_relation(self):
        memory = MemoryItem(
            kind="limitation",
            statement="Context length limits dialogue continuity.",
            evidence_quote="context length limits dialogue continuity",
            location="P01|chunk=P01:fulltext:1",
            subject="context length",
            relation="limits",
            object="dialogue continuity",
        )
        self.assertEqual(memory.importance, 3)
        self.assertEqual(memory.relation, "limits")

    def test_layout_interleaving_match(self):
        corpus = {
            "c1": {
                "text": "The fine-tuning used 600 examples from SocratiQ that were annotated through Amazon Mechanical Turk unrelated column text crowdsourcing platform."
            }
        }
        self.assertTrue(
            layout_quote_matches(
                "600 examples from SocratiQ that were annotated through Amazon Mechanical Turk crowdsourcing platform",
                ["P01|chunk=c1"],
                corpus,
            )
        )

    def test_layout_interleaving_inside_hyphenated_word(self):
        corpus = {
            "c1": {
                "text": "The sample comprises 22 educators from nine coun- unrelated column text tries and five continents."
            }
        }
        self.assertTrue(
            layout_quote_matches(
                "The sample comprises 22 educators from nine countries and five continents.",
                ["P01|chunk=c1"],
                corpus,
            )
        )

    def test_layout_interleaving_prefix_attached_to_expected_word(self):
        corpus = {
            "c1": {
                "text": "Codex ranks 17 amongst the 71 students placing it within the top ques- quartile of class performance."
            }
        }
        self.assertTrue(
            layout_quote_matches(
                "Codex ranks 17 amongst the 71 students placing it within the top quartile of class performance.",
                ["P01|chunk=c1"],
                corpus,
            )
        )

    def test_consolidation_selects_ids_without_rewriting_evidence(self):
        class FakeLLM:
            def with_structured_output(self, schema, method):
                self.schema = schema
                return self

            def invoke(self, messages):
                return PaperConsolidation(
                    one_sentence_summary="Summary",
                    study_design="Review",
                    selected_memory_ids=["part-002-memory-001"],
                )

        first = PaperMemory(
            one_sentence_summary="First",
            study_design="Review",
            memories=[
                MemoryItem(
                    kind="finding",
                    statement="First statement.",
                    importance=4,
                    evidence_quote="first exact quote",
                    location="P01|chunk=c1",
                )
            ],
        )
        second = PaperMemory(
            one_sentence_summary="Second",
            study_design="Review",
            memories=[
                MemoryItem(
                    kind="limitation",
                    statement="Second statement.",
                    importance=5,
                    evidence_quote="second exact quote",
                    location="P01|chunk=c2",
                )
            ],
        )
        corpus = {
            "c1": {"text": "first exact quote"},
            "c2": {"text": "second exact quote"},
        }
        result = consolidate_memory(FakeLLM(), [first, second], 32, corpus)
        selected = {(item.evidence_quote, item.location) for item in result.memories}
        self.assertIn(("second exact quote", "P01|chunk=c2"), selected)

    def test_rebuild_outputs_keeps_bibtex_and_source_pointer(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = Path(temporary) / "Postgraduate_Test"
            base = vault / "rag/paper-memory"
            papers = base / "papers"
            papers.mkdir(parents=True)
            wrapper = {
                "bibliography": {
                    "paper_id": "P01",
                    "title": "Example",
                    "authors": ["Ada Lovelace"],
                    "year_source": "2026, Venue",
                    "year": "2026",
                    "url": "https://example.test",
                    "doi": "10.1000/example",
                    "citation_key": "example2026",
                    "bibtex": "@article{example2026}",
                    "paper_card": "wiki/papers/P01-example.md",
                },
                "paper_memory": {
                    "one_sentence_summary": "Summary",
                    "study_design": "Experiment",
                    "population": "Students",
                    "intervention": "Tutor",
                    "comparator": "Control",
                    "outcomes": ["Learning"],
                    "affiliations": ["Example University"],
                },
                "validated_memories": [
                    {
                        "memory_id": "P01-M001",
                        "kind": "causal_claim",
                        "statement": "Tutor improved learning.",
                        "importance": 5,
                        "evidence_quote": "improved learning",
                        "location": "P01|chunk=P01:fulltext:1",
                        "boundary": "Students",
                        "causal_status": "identified_causal_effect",
                        "role": "",
                        "entities": ["Tutor", "Learning"],
                        "subject": "Tutor",
                        "relation": "causes",
                        "object": "Learning",
                        "source_chunk_ids": ["P01:fulltext:1"],
                        "review_status": "machine-validated",
                    }
                ],
            }
            (papers / "P01.json").write_text(json.dumps(wrapper))
            rebuild_outputs(base, vault)
            records = [json.loads(line) for line in (base / "corpus.jsonl").read_text().splitlines()]
            self.assertEqual(len(records), 3)
            self.assertIn("@article{example2026}", records[0]["text"])
            self.assertEqual(records[2]["metadata"]["source_chunk_ids"], ["P01:fulltext:1"])
            edge = json.loads((base / "causal-edges.jsonl").read_text())
            self.assertEqual(edge["memory_id"], "P01-M001")


if __name__ == "__main__":
    unittest.main()

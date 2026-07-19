import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from generate_postgraduate_profile import build_profile, write_profile


class PostgraduateProfileTests(unittest.TestCase):
    def test_profile_counts_sources_and_writes_all_outputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = Path(temporary) / "Postgraduate_Test_Domain"
            papers = vault / "wiki/papers"
            memories = vault / "rag/paper-memory/papers"
            papers.mkdir(parents=True)
            memories.mkdir(parents=True)

            (papers / "P01-example.md").write_text(
                """---
status: fulltext-read
evidence_level: verified-fulltext
venue: TestConf
---
# P01
""",
                encoding="utf-8",
            )
            (papers / "P02-blocked.md").write_text(
                """---
status: fulltext-blocked
evidence_level: blocked
---
# P02
""",
                encoding="utf-8",
            )
            wrapper = {
                "paper_id": "P01",
                "validated_memories": [
                    {
                        "kind": "finding",
                        "evidence_match": "exact",
                        "review_status": "machine-reviewed",
                        "causal_status": "reported_association",
                        "entities": ["Tutor", "Student"],
                    },
                    {
                        "kind": "experiment",
                        "evidence_match": "layout-recovered",
                        "review_status": "human-verified",
                        "causal_status": "identified_causal_effect",
                        "entities": ["Tutor"],
                    },
                ],
            }
            (memories / "P01.json").write_text(json.dumps(wrapper), encoding="utf-8")

            memory_root = vault / "rag/paper-memory"
            (memory_root / "causal-edges.jsonl").write_text(json.dumps({"source": "A", "target": "B"}) + "\n", encoding="utf-8")
            (memory_root / "corpus.jsonl").write_text(json.dumps({"id": "m1"}) + "\n", encoding="utf-8")
            (vault / "rag/corpus.jsonl").write_text(
                json.dumps({"id": "r1", "metadata": {"source_type": "paper-fulltext", "rag_evidence_level": "verified-fulltext"}}) + "\n",
                encoding="utf-8",
            )

            for relative in ["variables/v.md", "mechanisms/m.md", "datasets/d.md", "claims/c.md", "relations/r.md"]:
                path = vault / "wiki" / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("# Test\n", encoding="utf-8")
            for name in ["index.md", "hot.md", "log.md"]:
                (vault / "wiki" / name).write_text(f"# {name}\n", encoding="utf-8")

            profile = build_profile(vault, "en")
            self.assertEqual(profile["counts"]["paper_cards"], 2)
            self.assertEqual(profile["counts"]["blocked_papers"], 1)
            self.assertEqual(profile["counts"]["validated_memories"], 2)
            self.assertEqual(profile["counts"]["causal_edges"], 1)
            self.assertEqual(profile["top_entities"][0], {"name": "Tutor", "count": 2})
            self.assertEqual(len(profile["task_fit"]), 6)

            outputs = write_profile(vault, profile)
            self.assertTrue(outputs["markdown"].exists())
            self.assertTrue(outputs["html"].exists())
            self.assertTrue(outputs["json"].exists())
            self.assertIn("POSTGRADUATE-PROFILE-START", (vault / "wiki/index.md").read_text(encoding="utf-8"))
            self.assertIn("Capability Visualization", outputs["markdown"].read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

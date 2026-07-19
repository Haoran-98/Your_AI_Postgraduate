import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from query_paper_memory_rag import retrieve


class QueryPaperMemoryRagTest(unittest.TestCase):
    def test_retrieval_rehydrates_source_and_bibliography(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = Path(temporary)
            (vault / "rag/paper-memory").mkdir(parents=True)
            bibliography_id = "Test:P01:bibliography"
            memory_records = [
                {
                    "id": bibliography_id,
                    "text": "Example citation",
                    "metadata": {
                        "source_type": "paper-bibliography",
                        "paper_id": "P01",
                        "bibtex": "@article{example}",
                    },
                },
                {
                    "id": "Test:P01:memory:P01-M001",
                    "text": "finding: final answer accuracy hides dialogue errors",
                    "metadata": {
                        "source_type": "paper-memory",
                        "paper_id": "P01",
                        "memory_id": "P01-M001",
                        "memory_kind": "finding",
                        "location": "P01|chunk=c1",
                        "source_chunk_ids": ["c1"],
                        "bibliography_ref": bibliography_id,
                    },
                },
            ]
            (vault / "rag/paper-memory/corpus.jsonl").write_text(
                "\n".join(json.dumps(item) for item in memory_records) + "\n"
            )
            (vault / "rag/corpus.jsonl").write_text(
                json.dumps({"id": "c1", "text": "source evidence", "metadata": {}}) + "\n"
            )
            result = retrieve(vault, "dialogue errors", 3)[0]
            self.assertEqual(result["memory_id"], "P01-M001")
            self.assertEqual(result["source_chunks"][0]["text"], "source evidence")
            self.assertEqual(result["bibliography"]["metadata"]["bibtex"], "@article{example}")


if __name__ == "__main__":
    unittest.main()

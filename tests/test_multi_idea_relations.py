import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import generate_semantic_relations as semantic
import generate_vault_relations as relations


class MultiIdeaRelationTests(unittest.TestCase):
    def test_requested_idea_uses_only_its_paper_master(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = Path(temporary) / "Postgraduate_Test"
            wiki = vault / "wiki"
            for folder in ("ideas", "papers", "relations", "surveys", "sources"):
                (wiki / folder).mkdir(parents=True, exist_ok=True)
            for name in ("index.md", "hot.md", "log.md"):
                (wiki / name).write_text(f"# {name}\n", encoding="utf-8")

            (wiki / "ideas/idea-01-old.md").write_text("# Old\n", encoding="utf-8")
            (wiki / "ideas/idea-02-new.md").write_text("# New\n", encoding="utf-8")
            (wiki / "papers/idea-02-paper-master.csv").write_text(
                "id,title\nP51,Target Paper\n", encoding="utf-8"
            )
            (wiki / "papers/P01-old.md").write_text("# Old Paper\n", encoding="utf-8")
            (wiki / "papers/P51-target.md").write_text("# Target Paper\n", encoding="utf-8")

            stats = relations.process_vault(vault, "2026-07-23", False, "idea-02")
            self.assertEqual(stats.idea_id, "idea-02")
            self.assertEqual(stats.papers, 1)
            relation_map = (wiki / "relations/idea-02-relation-map.md").read_text(encoding="utf-8")
            self.assertIn("P51", relation_map)
            self.assertNotIn("P01", relation_map)

            semantic_stats = semantic.process_vault(vault, "2026-07-23", False, 2, 80, "idea-02")
            self.assertEqual(semantic_stats["idea_id"], "idea-02")
            self.assertEqual(semantic_stats["papers"], 1)


if __name__ == "__main__":
    unittest.main()

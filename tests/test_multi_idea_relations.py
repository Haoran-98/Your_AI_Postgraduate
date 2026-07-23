import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import generate_semantic_relations as semantic
import generate_vault_relations as relations
import prepare_rag_corpus as rag_builder


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

    def test_global_readme_keeps_all_discovered_relation_maps(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "README.md").write_text("# Root\n", encoding="utf-8")
            for vault_name, idea_id in (("Postgraduate_A", "idea-01"), ("Postgraduate_B", "idea-02")):
                relation_dir = root / vault_name / "wiki/relations"
                relation_dir.mkdir(parents=True)
                (relation_dir / f"{idea_id}-relation-map.md").write_text("# Map\n", encoding="utf-8")

            relations.update_global_readme(root, [], False)
            readme = (root / "README.md").read_text(encoding="utf-8")
            self.assertIn("Postgraduate_A/wiki/relations/idea-01-relation-map.md", readme)
            self.assertIn("Postgraduate_B/wiki/relations/idea-02-relation-map.md", readme)

    def test_multi_idea_vault_gets_vault_level_rag_note(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = Path(temporary) / "Postgraduate_Test"
            (vault / "wiki").mkdir(parents=True)
            (vault / "wiki/index.md").write_text("# Index\n", encoding="utf-8")
            manifest = {
                "idea_id": "multiple",
                "idea_ids": ["idea-01", "idea-02"],
                "generated": "2026-07-23",
                "records": 2,
                "source_type_counts": {"paper-fulltext": 2},
                "hyperextract_status": "pending-model-execution",
            }

            rag_builder.write_vault_rag_note(vault, manifest)
            note = vault / "wiki/relations/vault-rag-layer.md"
            self.assertTrue(note.exists())
            self.assertIn('idea_ids: ["idea-01", "idea-02"]', note.read_text(encoding="utf-8"))
            self.assertIn("vault-rag-layer", (vault / "wiki/index.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

import unittest

from sync_agent_pack import COPIES, PLUGIN, ROOT


class PluginCopiesTest(unittest.TestCase):
    def test_plugin_copies_match_their_sources(self):
        for source, target in COPIES.items():
            with self.subTest(source=source):
                self.assertEqual(
                    (PLUGIN / target).read_bytes(), (ROOT / source).read_bytes(),
                    f"{target} is out of date: run python3 scripts/sync_agent_pack.py",
                )


if __name__ == "__main__":
    unittest.main()

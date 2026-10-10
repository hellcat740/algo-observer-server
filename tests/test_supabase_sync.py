"""deploy/sync-supabase.py 的纯函数核心单测（不触数据库）。

运行（仓库根目录 / 容器内）：
    python -m unittest discover tests -v
"""
import importlib.util
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

_CANDIDATES = [
    Path(__file__).resolve().parent.parent / "deploy" / "sync-supabase.py",  # 仓库内
    Path(__file__).resolve().parent / "deploy" / "sync-supabase.py",        # tests 被单独拷贝的场景
]
_SCRIPT = next(p for p in _CANDIDATES if p.exists())
_spec = importlib.util.spec_from_file_location("sync_supabase", _SCRIPT)
sync_supabase = importlib.util.module_from_spec(_spec)
sys.modules["sync_supabase"] = sync_supabase
_spec.loader.exec_module(sync_supabase)


def row(obs_id: str, price: int, **extra):
    base = {"observation_id": obs_id, "display_price_cents": price, "synced_at": None}
    base.update(extra)
    return base


class DiffRowsTest(unittest.TestCase):
    def test_bidirectional_union(self):
        local = {"a": row("a", 100), "b": row("b", 200)}
        remote = {"b": row("b", 200), "c": row("c", 300)}
        push, pull, conflicts = sync_supabase.diff_rows(local, remote)
        self.assertEqual([r["observation_id"] for r in push], ["a"])
        self.assertEqual([r["observation_id"] for r in pull], ["c"])
        self.assertEqual(conflicts, [])

    def test_idempotent_when_equal(self):
        data = {"a": row("a", 100), "b": row("b", 200)}
        push, pull, conflicts = sync_supabase.diff_rows(data, dict(data))
        self.assertEqual((push, pull, conflicts), ([], [], []))

    def test_empty_both_sides(self):
        self.assertEqual(sync_supabase.diff_rows({}, {}), ([], [], []))

    def test_conflict_same_pk_different_content(self):
        local = {"a": row("a", 100)}
        remote = {"a": row("a", 999)}
        push, pull, conflicts = sync_supabase.diff_rows(local, remote)
        self.assertEqual((push, pull), ([], []))
        self.assertEqual(conflicts, ["a"])

    def test_no_conflict_when_only_synced_at_differs(self):
        local = {"a": row("a", 100, synced_at=datetime(2026, 10, 1, tzinfo=timezone.utc))}
        remote = {"a": row("a", 100, synced_at=None)}
        _, _, conflicts = sync_supabase.diff_rows(local, remote)
        self.assertEqual(conflicts, [])

    def test_datetime_normalized_for_comparison(self):
        ts = datetime(2026, 10, 1, 12, 0, 0, tzinfo=timezone.utc)
        local = {"a": row("a", 100, fetch_ts=ts)}
        remote = {"a": row("a", 100, fetch_ts=ts.isoformat())}
        _, _, conflicts = sync_supabase.diff_rows(local, remote)
        self.assertEqual(conflicts, [])

    def test_missing_column_treated_as_none(self):
        # 远端老库缺 origin 列 → 按 None 参与比对，与本地值不同即报冲突（保守策略：
        # 宁可报冲突人工裁决，也不静默判定一致而漏掉真实差异）
        local = {"a": row("a", 100, origin="local")}
        remote = {"a": row("a", 100)}
        _, _, conflicts = sync_supabase.diff_rows(local, remote)
        self.assertEqual(conflicts, ["a"])


if __name__ == "__main__":
    unittest.main()

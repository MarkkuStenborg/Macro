# ============================================================================
# File: macro_dashboard/macro/store.py
# ============================================================================

# Tallennuspaikka: C:\Users\markk\Talous\macro_dashboard\macro\store.py
"""Haetun lähdedatan paikallinen varasto (CSV + index.json).

Haku ja sivun rakennus erotetaan: ``update`` kirjoittaa varastoon, ``pages`` lukee sieltä.
Varasto on kansio ``store/``: ``raw/<avain>.csv`` (date,value) ja ``index.json`` (metatiedot).
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

__all__ = ["Store"]


class Store:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self._raw = self.root / "raw"
        self._raw.mkdir(parents=True, exist_ok=True)
        self._index_path = self.root / "index.json"
        self._lock = threading.Lock()
        self._index: dict[str, dict[str, Any]] = (
            json.loads(self._index_path.read_text(encoding="utf-8")) if self._index_path.exists() else {}
        )

    # -- lähdesarjat ------------------------------------------------------

    def is_fresh(self, key: str, max_age_hours: float) -> bool:
        m = self._index.get(key)
        if not m or m.get("error") or not (self._raw / f"{key}.csv").exists():
            return False
        age = datetime.now() - datetime.fromisoformat(m["fetched_at"])
        return age < timedelta(hours=max_age_hours)

    def save(self, key: str, s: pd.Series, meta: dict[str, Any]) -> None:
        s = s.dropna()
        s.rename("value").rename_axis("date").to_csv(self._raw / f"{key}.csv")
        with self._lock:
            self._index[key] = {
                **meta, "fetched_at": datetime.now().isoformat(timespec="seconds"),
                "n": int(len(s)), "last_obs": s.index[-1].strftime("%Y-%m-%d") if len(s) else None,
                "error": None,
            }

    def save_error(self, key: str, meta: dict[str, Any], error: str) -> None:
        with self._lock:
            self._index[key] = {**meta, "fetched_at": datetime.now().isoformat(timespec="seconds"),
                                "n": 0, "last_obs": None, "error": error[:400]}

    def load(self, key: str) -> pd.Series | None:
        p = self._raw / f"{key}.csv"
        if not p.exists():
            return None
        df = pd.read_csv(p, parse_dates=["date"], index_col="date")
        return df["value"].astype("float64")

    def meta(self, key: str) -> dict[str, Any] | None:
        return self._index.get(key)

    def flush(self) -> None:
        with self._lock:
            self._index_path.write_text(json.dumps(self._index, indent=1, ensure_ascii=False), encoding="utf-8")

    # -- ratkaisu: mikä ehdokas voitti kullekin sarjalle ------------------

    def save_resolved(self, resolved: dict[str, dict[str, Any]]) -> None:
        (self.root / "resolved.json").write_text(
            json.dumps(resolved, indent=1, ensure_ascii=False), encoding="utf-8")

    def load_resolved(self) -> dict[str, dict[str, Any]]:
        p = self.root / "resolved.json"
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}

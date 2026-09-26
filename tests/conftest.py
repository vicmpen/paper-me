import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["WEBAPP_DISABLE_SCHEDULER"] = "1"


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    from webapp import db
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "t.db")
    db.init_db()
    return db

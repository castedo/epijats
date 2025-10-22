import json
from collections import Counter

def check_conditions(case_dir, issues):
    conditions_path = case_dir / "conditions.json"
    if not conditions_path.exists():
        assert not issues
    else:
        with open(conditions_path, "r") as f:
            conditions = Counter(i.condition for i in issues)
            assert [c.as_pod() for c in conditions] == json.load(f)

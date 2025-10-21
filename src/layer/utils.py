import json
from typing import Any, Dict, List, Tuple

from sqlalchemy import and_, or_, not_, true, false
from sqlalchemy.sql.expression import BinaryExpression

def parse_filters(raw) -> List[Dict[str, Any]]:
    if raw is None:
        return []
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            raise ValueError("filters must be valid JSON")
    if isinstance(raw, list):
        return raw
    raise ValueError("filters must be an array")

def build_where(rules: List[Dict[str, Any]]) -> BinaryExpression:
    clauses: List[BinaryExpression] = []

    for r in rules:
        if not isinstance(r, dict):
            continue
        col = r.get("field")
        op = r.get("op")
        value = r.get("value")
        inclusive = r.get("inclusive", True)

        # BETWEEN / NOT BETWEEN
        if op in ("BETWEEN", "NOT BETWEEN"):
            if not isinstance(value, list):
                raise ValueError("BETWEEN requires [min, max]")
            a, b = (value + [None, None])[:2]
            # нормализуем порядок, если оба заданы и сравнимы
            try:
                if a is not None and b is not None and a > b:
                    a, b = b, a
            except Exception:
                pass

            if a is None and b is None:
                continue

            if a is not None and b is not None:
                expr = col.between(a, b) if inclusive else and_(col > a, col < b)
                if op == "NOT BETWEEN":
                    expr = not_(expr) if inclusive else or_(col <= a, col >= b)
                clauses.append(expr)
                continue
            if a is not None:
                expr = (col >= a) if inclusive else (col > a)
                if op == "NOT BETWEEN":
                    expr = (col < a) if inclusive else (col <= a)
                clauses.append(expr)
                continue
            if b is not None:
                expr = (col <= b) if inclusive else (col < b)
                if op == "NOT BETWEEN":
                    expr = (col > b) if inclusive else (col >= b)
                clauses.append(expr)
                continue

        # IN
        elif op == "IN":
            if not isinstance(value, list):
                raise ValueError("IN requires array value")
            clauses.append(false() if len(value) == 0 else col.in_(value))

        # ILIKE
        elif op == "ILIKE":
            if value is None:  # игнорируем пустую маску
                continue
            clauses.append(col.ilike(str(value)))

        # базовые сравнения
        elif op in ("=", "!=", ">", ">=", "<", "<="):
            if op == "=":   clauses.append(col == value)
            if op == "!=":  clauses.append(col != value)
            if op == ">":   clauses.append(col >  value)
            if op == ">=":  clauses.append(col >= value)
            if op == "<":   clauses.append(col <  value)
            if op == "<=":  clauses.append(col <= value)

    return and_(*clauses) if clauses else true()

def parse_order(raw: str | None) -> List[Tuple[str, str]]:
    if not raw:
        return []
    out: List[Tuple[str, str]] = []
    for part in str(raw).split(","):
        part = part.strip()
        if not part: 
            continue
        col, dir_ = (part.split(":", 1) + ["asc"])[:2]
        col = col.strip()
        dir_ = dir_.strip().lower()
        if dir_ not in ("asc", "desc"):
            raise ValueError("Bad order direction (asc/desc)")
        out.append((col, dir_))
    return out
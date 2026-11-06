"""Deterministic query-plan validator (reused by data generation, evaluation, inference, API).

validate_plan(plan, schema) -> list of error strings. Empty list == plan is valid.
Nothing here trusts the model: tables, columns, operators, value types, joins and limits are
all checked against the REAL schema.
"""
import datetime
import json
import re

from app.slm_search.schema import Schema

SEARCH_KEYS_SQL = ["operation", "table", "select", "filters", "joins", "group_by", "aggregations", "sort", "limit"]
SEARCH_KEYS_MONGO = ["operation", "collection", "select", "filters", "joins", "group_by", "aggregations", "sort", "limit"]
REFUSE_REASONS = {"unknown_table", "unknown_column", "unauthorized_table", "write_operation"}
CLARIFY_REASONS = {"ambiguous_column", "vague_request"}
OPERATORS_BY_TYPE = {
    "int": {"equals", "not_equals", "greater_than", "less_than", "greater_or_equal", "less_or_equal",
            "between", "in", "is_null", "is_not_null"},
    "float": {"equals", "not_equals", "greater_than", "less_than", "greater_or_equal", "less_or_equal",
              "between", "in", "is_null", "is_not_null"},
    "text": {"equals", "not_equals", "contains", "starts_with", "in", "is_null", "is_not_null"},
    "date": {"equals", "not_equals", "greater_than", "less_than", "greater_or_equal", "less_or_equal",
             "between", "is_null", "is_not_null"},
    "bool": {"equals", "is_null", "is_not_null"},
}
AGG_FUNCS = {"count", "sum", "avg", "min", "max"}
ALIAS_RE = re.compile(r"^[a-z][a-z0-9_]*$")
MAX_LIMIT = 1000
MAX_IN = 20
MAX_JOINS = 2
MAX_STR = 100


def _is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _check_value(v, typ):
    if typ == "int":
        return isinstance(v, int) and not isinstance(v, bool)
    if typ == "float":
        return _is_num(v)
    if typ == "text":
        return isinstance(v, str) and 0 < len(v) <= MAX_STR and all(ord(ch) >= 32 for ch in v)
    if typ == "date":
        try:
            return isinstance(v, str) and datetime.date.fromisoformat(v).isoformat() == v
        except ValueError:
            return False
    if typ == "bool":
        return isinstance(v, bool)
    return False


def dump_plan(plan):
    """Canonical JSON: fixed key order, compact, no ASCII escaping."""
    return json.dumps(canonicalize(plan), separators=(",", ":"), ensure_ascii=False)


def canonicalize(plan):
    def cond(c):
        if "or" in c:
            return {"or": [cond(x) for x in c["or"]]}
        key = "column" if "column" in c else "field"
        return {key: c[key], "operator": c["operator"], "value": c["value"]}

    op = plan.get("operation")
    if op in ("refuse", "clarify"):
        return {"operation": op, "reason": plan["reason"], "detail": plan["detail"]}
    keys = SEARCH_KEYS_MONGO if "collection" in plan else SEARCH_KEYS_SQL
    out = {}
    for k in keys:
        v = plan[k]
        if k == "filters":
            v = [cond(c) for c in v]
        elif k == "joins":
            v = [{"table": j["table"], "left": j["left"], "right": j["right"]} for j in v]
        elif k == "aggregations":
            v = [{"function": a["function"], "column": a["column"], "alias": a["alias"]} for a in v]
        elif k == "sort":
            v = [{"column": s["column"], "direction": s["direction"]} for s in v]
        out[k] = v
    return out


def validate_plan(plan, schema: Schema):
    errs = []
    if not isinstance(plan, dict):
        return ["plan is not an object"]
    op = plan.get("operation")
    if op in ("refuse", "clarify"):
        return _validate_non_search(plan, schema, op)
    if op != "search":
        return [f"unknown operation {op!r}"]

    mongo = schema.dialect == "mongo"
    keys = SEARCH_KEYS_MONGO if mongo else SEARCH_KEYS_SQL
    if set(plan) != set(keys):
        return [f"keys must be exactly {keys}, got {sorted(plan)}"]

    base_name = plan[keys[1]]
    base = schema.table(base_name) if isinstance(base_name, str) else None
    if base is None:
        return [f"unknown {keys[1]} {base_name!r}"]
    if not schema.is_allowed(base_name):
        return [f"{keys[1]} {base_name!r} is not allowed for this user"]

    # ---- joins
    joined = {base_name: base}
    joins = plan["joins"]
    if not isinstance(joins, list):
        return ["joins must be a list"]
    if mongo and joins:
        errs.append("mongo plans cannot have joins")
    if len(joins) > MAX_JOINS:
        errs.append(f"too many joins (max {MAX_JOINS})")
    for j in joins if not mongo else []:
        if not isinstance(j, dict) or set(j) != {"table", "left", "right"}:
            errs.append("join must have exactly table,left,right")
            continue
        jt = schema.table(j["table"]) if isinstance(j["table"], str) else None
        if jt is None:
            errs.append(f"join table {j['table']!r} unknown")
            continue
        if not schema.is_allowed(jt.name):
            errs.append(f"join table {jt.name!r} not allowed")
            continue
        if jt.name in joined:
            errs.append(f"table {jt.name!r} joined twice")
            continue
        ok = False
        for other in list(joined):
            e1, e2 = schema.fk_edge(other, jt.name), schema.fk_edge(jt.name, other)
            if e1 and {j["left"], j["right"]} == {f"{other}.{e1[0]}", f"{jt.name}.{e1[1]}"}:
                ok = True
            if e2 and {j["left"], j["right"]} == {f"{jt.name}.{e2[0]}", f"{other}.{e2[1]}"}:
                ok = True
        if not ok:
            errs.append(f"join {j['left']} = {j['right']} is not a declared foreign key")
        joined[jt.name] = jt
    qualified = bool(joins) and not mongo

    def resolve(ref, allow_star=False):
        """Return column type, or None (and record error)."""
        if not isinstance(ref, str):
            errs.append(f"column ref {ref!r} is not a string")
            return None
        if qualified:
            if "." not in ref:
                errs.append(f"column {ref!r} must be qualified as table.column when joining")
                return None
            t, c = ref.split(".", 1)
            tab = joined.get(t)
            if tab is None:
                errs.append(f"column {ref!r}: table {t!r} is not part of the query")
                return None
            if c == "*" and allow_star:
                return "*"
            col = tab.column(c)
        else:
            if ref == "*" and allow_star:
                return "*"
            col = base.column(ref)
        if col is None:
            errs.append(f"unknown column {ref!r}")
            return None
        return col.type

    # ---- aggregations first (aliases are legal in sort)
    aggs, aliases = plan["aggregations"], set()
    if not isinstance(aggs, list):
        return errs + ["aggregations must be a list"]
    for a in aggs:
        if not isinstance(a, dict) or set(a) != {"function", "column", "alias"}:
            errs.append("aggregation must have exactly function,column,alias")
            continue
        if a["function"] not in AGG_FUNCS:
            errs.append(f"bad aggregation function {a['function']!r}")
            continue
        if a["column"] == "*":
            if a["function"] != "count":
                errs.append("only count may use '*'")
        else:
            t = resolve(a["column"])
            if t is not None:
                if a["function"] in ("sum", "avg") and t not in ("int", "float"):
                    errs.append(f"{a['function']} needs a numeric column")
                if a["function"] in ("min", "max") and t not in ("int", "float", "date"):
                    errs.append(f"{a['function']} needs a numeric or date column")
        if not isinstance(a["alias"], str) or not ALIAS_RE.match(a["alias"]) or a["alias"] in aliases:
            errs.append(f"bad or duplicate alias {a['alias']!r}")
        else:
            aliases.add(a["alias"])

    # ---- group_by / select
    gb, sel = plan["group_by"], plan["select"]
    if not isinstance(gb, list) or not isinstance(sel, list):
        return errs + ["group_by and select must be lists"]
    for g in gb:
        resolve(g)
    if gb and not aggs:
        errs.append("group_by requires at least one aggregation")
    if aggs:
        if not set(sel) <= set(gb):
            errs.append("with aggregations, select may only contain group_by columns")
    else:
        if not sel:
            errs.append("select must not be empty")
        for s in sel:
            if s == "*" and len(sel) > 1:
                errs.append("'*' cannot be mixed with other columns")
            resolve(s, allow_star=True)
    if len(set(sel)) != len(sel):
        errs.append("duplicate select columns")

    # ---- filters
    fkey = "field" if mongo else "column"

    def check_cond(c, depth=0):
        if not isinstance(c, dict):
            errs.append("filter must be an object")
            return
        if "or" in c:
            if depth or set(c) != {"or"} or not isinstance(c["or"], list) or len(c["or"]) < 2:
                errs.append("'or' group must be top-level with >=2 conditions")
                return
            for x in c["or"]:
                check_cond(x, depth + 1)
            return
        if set(c) != {fkey, "operator", "value"}:
            errs.append(f"condition must have exactly {fkey},operator,value")
            return
        t = resolve(c[fkey])
        if t is None or t == "*":
            return
        o, v = c["operator"], c["value"]
        if o not in OPERATORS_BY_TYPE[t]:
            errs.append(f"operator {o!r} not allowed on {t} column {c[fkey]!r}")
            return
        if o in ("is_null", "is_not_null"):
            if v is not None:
                errs.append("is_null/is_not_null value must be null")
        elif o == "between":
            if not (isinstance(v, list) and len(v) == 2 and all(_check_value(x, t) for x in v)):
                errs.append("between needs [low, high] of the column type")
            elif v[0] > v[1]:
                errs.append("between low > high")
        elif o == "in":
            if not (isinstance(v, list) and 1 <= len(v) <= MAX_IN and all(_check_value(x, t) for x in v)):
                errs.append("in needs a non-empty list of the column type")
        elif not _check_value(v, t):
            errs.append(f"value {v!r} does not fit {t} column {c[fkey]!r}")

    if not isinstance(plan["filters"], list):
        errs.append("filters must be a list")
    else:
        for c in plan["filters"]:
            check_cond(c)

    # ---- sort / limit
    if not isinstance(plan["sort"], list):
        errs.append("sort must be a list")
    else:
        for s in plan["sort"]:
            if not isinstance(s, dict) or set(s) != {"column", "direction"} or s["direction"] not in ("asc", "desc"):
                errs.append("sort item must be {column, direction asc|desc}")
            elif s["column"] not in aliases:
                resolve(s["column"])
    lim = plan["limit"]
    if not (isinstance(lim, int) and not isinstance(lim, bool) and 1 <= lim <= MAX_LIMIT):
        errs.append(f"limit must be an integer 1..{MAX_LIMIT}")
    return errs


def _validate_non_search(plan, schema, op):
    if set(plan) != {"operation", "reason", "detail"}:
        return ["refuse/clarify must have exactly operation,reason,detail"]
    reasons = REFUSE_REASONS if op == "refuse" else CLARIFY_REASONS
    r, d = plan["reason"], plan["detail"]
    if r not in reasons:
        return [f"bad {op} reason {r!r}"]
    if not isinstance(d, str) or not d or len(d) > MAX_STR:
        return ["detail must be a short non-empty string"]
    lower_tables = {t.name.lower() for t in schema.tables}
    lower_cols = {c.name.lower() for t in schema.tables for c in t.columns}
    # Consistency with the real schema (so the label is actually true):
    if r == "unknown_table" and d.lower() in lower_tables:
        return [f"table {d!r} exists, so it is not unknown"]
    if r == "unknown_column" and d.lower() in lower_cols:
        return [f"column {d!r} exists, so it is not unknown"]
    if r == "unauthorized_table" and not (schema.table(d) and not schema.is_allowed(d)):
        return [f"{d!r} is not a known, disallowed table"]
    if r == "ambiguous_column":
        owners = [t for t in schema.tables if t.column(d) and schema.is_allowed(t.name)]
        if len(owners) < 2:
            return [f"column {d!r} is not ambiguous"]
    return []

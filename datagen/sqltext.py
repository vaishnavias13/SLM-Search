"""Render a plan as SQL / Mongo TEXT. Used ONLY to make plain pretraining text and to show humans.

This text is never executed anywhere. (The real executor in Phase 10 builds parameterized
queries from validated plans; it does not use this module.)
"""
import json

OPS = {"equals": "=", "not_equals": "!=", "greater_than": ">", "less_than": "<", "greater_or_equal": ">=",
       "less_or_equal": "<="}
MONGO_OPS = {"equals": "$eq", "not_equals": "$ne", "greater_than": "$gt", "less_than": "$lt",
             "greater_or_equal": "$gte", "less_or_equal": "$lte", "in": "$in"}


def _lit(v):
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, str):
        return "'" + v.replace("'", "''") + "'"
    return str(v)


def _cond_sql(c):
    if "or" in c:
        return "(" + " OR ".join(_cond_sql(x) for x in c["or"]) + ")"
    col, op, v = c["column"], c["operator"], c["value"]
    if op in OPS:
        return f"{col} {OPS[op]} {_lit(v)}"
    if op == "between":
        return f"{col} BETWEEN {_lit(v[0])} AND {_lit(v[1])}"
    if op == "in":
        return f"{col} IN ({', '.join(_lit(x) for x in v)})"
    if op == "contains":
        return f"{col} LIKE {_lit('%' + v + '%')}"
    if op == "starts_with":
        return f"{col} LIKE {_lit(v + '%')}"
    return f"{col} IS NULL" if op == "is_null" else f"{col} IS NOT NULL"


def sql_text(plan):
    cols = list(plan["select"]) if plan["select"] else []
    for a in plan["aggregations"]:
        cols.append(f"{a['function'].upper()}({a['column']}) AS {a['alias']}")
    out = f"SELECT {', '.join(cols)} FROM {plan['table']}"
    for j in plan["joins"]:
        out += f" JOIN {j['table']} ON {j['left']} = {j['right']}"
    if plan["filters"]:
        out += " WHERE " + " AND ".join(_cond_sql(c) for c in plan["filters"])
    if plan["group_by"]:
        out += " GROUP BY " + ", ".join(plan["group_by"])
    if plan["sort"]:
        out += " ORDER BY " + ", ".join(f"{s['column']} {s['direction'].upper()}" for s in plan["sort"])
    return out + f" LIMIT {plan['limit']};"


def _mcond(c):
    if "or" in c:
        return {"$or": [_mcond(x) for x in c["or"]]}
    f, op, v = c["field"], c["operator"], c["value"]
    if op in MONGO_OPS:
        return {f: {MONGO_OPS[op]: v}}
    if op == "between":
        return {f: {"$gte": v[0], "$lte": v[1]}}
    if op == "contains":
        return {f: {"$regex": v}}
    if op == "starts_with":
        return {f: {"$regex": "^" + v}}
    return {f: None} if op == "is_null" else {f: {"$ne": None}}


def mongo_text(plan):
    flt = {"$and": [_mcond(c) for c in plan["filters"]]} if len(plan["filters"]) > 1 else \
        (_mcond(plan["filters"][0]) if plan["filters"] else {})
    coll = plan["collection"]
    if plan["aggregations"]:
        grp = {"_id": ("$" + plan["group_by"][0]) if plan["group_by"] else None}
        for a in plan["aggregations"]:
            grp[a["alias"]] = {"$sum": 1} if a["function"] == "count" else {"$" + a["function"]: "$" + a["column"]}
        return f"db.{coll}.aggregate({json.dumps([{'$match': flt}, {'$group': grp}], ensure_ascii=False)})"
    out = f"db.{coll}.find({json.dumps(flt, ensure_ascii=False)}"
    if plan["select"] != ["*"]:
        out += ", " + json.dumps({c: 1 for c in plan["select"]})
    out += ")"
    if plan["sort"]:
        out += ".sort(" + json.dumps({x["column"]: 1 if x["direction"] == "asc" else -1 for x in plan["sort"]}) + ")"
    return out + f".limit({plan['limit']})"


def plan_to_text(plan):
    if plan.get("operation") != "search":
        return None
    return mongo_text(plan) if "collection" in plan else sql_text(plan)

import copy

import pytest

from app.slm_search.schema import Schema
from app.slm_search.validator import dump_plan, validate_plan

SQL = Schema.from_text(
    "sql | allowed: customers, orders | "
    "customers(id int pk, name text, city text, age int, joined date, vip bool, balance float) ; "
    "orders(id int pk, customer_id int fk customers.id, total float, status text) ; "
    "payroll(id int pk, secret text, pay float)"
)
MONGO = Schema.from_text("mongo | allowed: products | products(sku text, price float, tags text)")


def search(**kw):
    p = {"operation": "search", "table": "customers", "select": ["*"], "filters": [], "joins": [],
         "group_by": [], "aggregations": [], "sort": [], "limit": 100}
    p.update(kw)
    return p


def test_schema_text_roundtrip():
    assert Schema.from_text(SQL.to_text()).to_text() == SQL.to_text()


def test_valid_plans_pass():
    assert validate_plan(search(), SQL) == []
    f = [{"column": "city", "operator": "equals", "value": "Pune"},
         {"or": [{"column": "age", "operator": "between", "value": [20, 30]},
                 {"column": "vip", "operator": "equals", "value": True}]}]
    assert validate_plan(search(filters=f, sort=[{"column": "age", "direction": "desc"}], limit=5), SQL) == []
    joined = search(table="orders", select=["orders.id", "customers.name"],
                    joins=[{"table": "customers", "left": "orders.customer_id", "right": "customers.id"}],
                    filters=[{"column": "customers.city", "operator": "equals", "value": "Pune"}])
    assert validate_plan(joined, SQL) == []
    agg = search(select=["city"], group_by=["city"],
                 aggregations=[{"function": "avg", "column": "age", "alias": "avg_age"}],
                 sort=[{"column": "avg_age", "direction": "desc"}])
    assert validate_plan(agg, SQL) == []
    assert validate_plan({"operation": "refuse", "reason": "unauthorized_table", "detail": "payroll"}, SQL) == []
    mongo = {"operation": "search", "collection": "products", "select": ["*"],
             "filters": [{"field": "price", "operator": "greater_than", "value": 1000}], "joins": [],
             "group_by": [], "aggregations": [], "sort": [], "limit": 10}
    assert validate_plan(mongo, MONGO) == []


@pytest.mark.parametrize("mutate", [
    lambda p: p.update(table="nope"),                                                # unknown table
    lambda p: p.update(table="payroll"),                                             # not allowed for user
    lambda p: p.update(table="customers; DROP TABLE customers"),                     # injection in identifier
    lambda p: p.update(select=["name; DROP TABLE x"]),                               # injection in column
    lambda p: p.update(select=["ghost"]),                                            # unknown column
    lambda p: p.update(filters=[{"column": "city", "operator": "LIKE %", "value": "x"}]),
    lambda p: p.update(filters=[{"column": "age", "operator": "contains", "value": "x"}]),   # op/type mismatch
    lambda p: p.update(filters=[{"column": "age", "operator": "equals", "value": "ten"}]),   # value/type mismatch
    lambda p: p.update(filters=[{"column": "age", "operator": "equals", "value": True}]),    # bool is not int
    lambda p: p.update(filters=[{"column": "joined", "operator": "equals", "value": "yesterday"}]),
    lambda p: p.update(filters=[{"column": "age", "operator": "between", "value": [30, 20]}]),
    lambda p: p.update(filters=[{"column": "city", "operator": "in", "value": []}]),
    lambda p: p.update(limit=0),
    lambda p: p.update(limit=10**9),
    lambda p: p.update(limit="100"),
    lambda p: p.update(sort=[{"column": "age", "direction": "sideways"}]),
    lambda p: p.update(joins=[{"table": "orders", "left": "customers.name", "right": "orders.status"}]),  # not an FK
    lambda p: p.update(joins=[{"table": "payroll", "left": "customers.id", "right": "payroll.id"}]),
    lambda p: p.update(aggregations=[{"function": "sum", "column": "city", "alias": "s"}]),
    lambda p: p.update(aggregations=[{"function": "drop", "column": "*", "alias": "s"}]),
    lambda p: p.update(group_by=["city"]),                                           # group_by without aggregation
    lambda p: p.update(extra="x"),                                                   # unexpected key
    lambda p: p.pop("limit"),                                                        # missing key
    lambda p: p.update(operation="delete"),
])
def test_bad_plans_are_rejected(mutate):
    p = copy.deepcopy(search())
    mutate(p)
    assert validate_plan(p, SQL), p


def test_unqualified_column_rejected_when_joining():
    p = search(table="orders", select=["status"],
               joins=[{"table": "customers", "left": "orders.customer_id", "right": "customers.id"}])
    assert validate_plan(p, SQL)


def test_mongo_rules():
    p = {"operation": "search", "collection": "products", "select": ["*"], "filters": [], "joins": [],
         "group_by": [], "aggregations": [], "sort": [], "limit": 10}
    bad_op = copy.deepcopy(p)
    bad_op["filters"] = [{"field": "price", "operator": "$where", "value": "sleep(5000)"}]
    assert validate_plan(bad_op, MONGO)
    bad_key = copy.deepcopy(p)
    bad_key["filters"] = [{"column": "price", "operator": "equals", "value": 1}]   # mongo uses "field"
    assert validate_plan(bad_key, MONGO)
    bad_join = copy.deepcopy(p)
    bad_join["joins"] = [{"table": "x", "left": "a.b", "right": "c.d"}]
    assert validate_plan(bad_join, MONGO)


def test_refusal_labels_must_be_true():
    assert validate_plan({"operation": "refuse", "reason": "unknown_table", "detail": "customers"}, SQL)  # exists
    assert validate_plan({"operation": "refuse", "reason": "unauthorized_table", "detail": "customers"}, SQL)  # allowed
    assert validate_plan({"operation": "refuse", "reason": "unknown_column", "detail": "name"}, SQL)  # exists
    assert validate_plan({"operation": "clarify", "reason": "ambiguous_column", "detail": "status"}, SQL)  # 1 owner
    assert validate_plan({"operation": "refuse", "reason": "made_up", "detail": "x"}, SQL)


def test_canonical_json_is_compact_and_ordered():
    p = search(filters=[{"value": 1, "operator": "equals", "column": "age"}])
    s = dump_plan(p)
    assert s.startswith('{"operation":"search","table":"customers","select":["*"],"filters":[{"column":"age"')
    assert " " not in s.replace("Pune", "")

"""Make a small GENERAL starter corpus for training the tokenizer (Phase 2).

This is NOT the synthetic database-search dataset (that is Phase 4). It is plain text:
English, SQL, database words, JSON and MongoDB snippets. It only exists so the tokenizer
has something to learn word pieces from. A bigger, licensed corpus is needed later.
"""
import random
from pathlib import Path

random.seed(7)
OUT = Path("data/raw/starter_corpus.txt")

FACTS = """A database stores information in tables.
A table contains rows and columns.
A primary key uniquely identifies a record.
A foreign key establishes a relationship between tables.
SQL SELECT statements retrieve records from a database.
The WHERE clause filters records.
The JOIN clause combines related tables.
GROUP BY groups records based on column values.
ORDER BY sorts query results.
LIMIT restricts the number of rows returned.
MongoDB stores documents inside collections.
A MongoDB aggregation pipeline processes documents.
PostgreSQL supports relational database queries.
MySQL supports SQL-based data retrieval.
SQL Server supports joins, indexes and stored procedures.
SQLite is a small database stored in a single file.
An index makes searching a column faster.
A transaction groups several changes so they succeed or fail together.
Read-only access means a user can look at data but cannot change it.
A parameterized query keeps user values separate from the SQL text.
Never trust text typed by a user without checking it first.
A schema describes the tables, columns and relationships of a database.
A query plan describes what to search for in a structured way.
Tenants are separate customers who share the same service.
Rate limiting stops one client from sending too many requests.""".splitlines()

TABLES = ["customers", "orders", "products", "employees", "invoices", "suppliers", "students",
          "courses", "patients", "doctors", "tickets", "payments", "books", "authors",
          "departments", "vehicles", "bookings", "reviews", "shipments", "accounts"]
COLS = ["id", "name", "city", "email", "price", "status", "created_at", "quantity", "salary",
        "country", "phone", "total", "category", "age", "rating", "title", "address",
        "first_name", "last_name", "order_date", "is_active", "department_id", "customer_id"]
CITIES = ["Bengaluru", "Mumbai", "Delhi", "Chennai", "Pune", "London", "Paris", "Berlin",
          "Tokyo", "Toronto", "Sydney", "Austin", "Boston", "Dubai", "Singapore"]
OPS = [("equals", "="), ("greater_than", ">"), ("less_than", "<"), ("not_equals", "!="),
       ("contains", "LIKE"), ("greater_or_equal", ">="), ("less_or_equal", "<=")]
AGGS = ["count", "sum", "avg", "min", "max"]
WORDS = ("find show list get give me all the every which who what how many customers people "
         "items records rows from in with where having more than less than at least at most "
         "between sorted by highest lowest newest oldest top first last per each total number "
         "of average sum maximum minimum count unique distinct please search look up display").split()


def rnd(xs):
    return random.choice(xs)


def sql_line():
    t, c, c2 = rnd(TABLES), rnd(COLS), rnd(COLS)
    kind = random.randint(0, 5)
    if kind == 0:
        return f"SELECT {c}, {c2} FROM {t} WHERE {c} = '{rnd(CITIES)}' LIMIT {rnd([10, 50, 100])};"
    if kind == 1:
        return f"SELECT COUNT(*) FROM {t} WHERE {c} > {random.randint(1, 5000)};"
    if kind == 2:
        return f"SELECT {c}, {rnd(AGGS).upper()}({c2}) FROM {t} GROUP BY {c} ORDER BY {c} DESC;"
    if kind == 3:
        t2 = rnd(TABLES)
        return (f"SELECT a.{c}, b.{c2} FROM {t} a JOIN {t2} b ON a.{rnd(COLS)} = b.{rnd(COLS)} "
                f"WHERE a.{c} < {random.randint(1, 999)};")
    if kind == 4:
        return f"SELECT * FROM {t} ORDER BY {c} ASC LIMIT {rnd([5, 20, 100])};"
    return f"SELECT DISTINCT {c} FROM {t} WHERE {c2} LIKE '%{rnd(CITIES)[:4].lower()}%';"


def json_line():
    t, c = rnd(TABLES), rnd(COLS)
    op = rnd(OPS)[0]
    val = rnd([f'"{rnd(CITIES)}"', str(random.randint(1, 9999)), "true", "null"])
    return ('{"operation": "search", "table": "%s", "filters": [{"column": "%s", '
            '"operator": "%s", "value": %s}], "limit": %d}' % (t, c, op, val, rnd([10, 50, 100])))


def mongo_line():
    t, c = rnd(TABLES), rnd(COLS)
    mop = rnd(["$gt", "$lt", "$eq", "$gte", "$lte", "$ne", "$in"])
    return f'db.{t}.find({{"{c}": {{"{mop}": {random.randint(1, 5000)}}}}}).limit({rnd([10, 100])})'


def schema_line():
    t = rnd(TABLES)
    cols = random.sample(COLS, random.randint(3, 6))
    typ = [rnd(["int", "text", "real", "date", "bool", "varchar"]) for _ in cols]
    return f"{t}(" + ", ".join(f"{c} {y}" for c, y in zip(cols, typ)) + ")"


def question_line():
    n = random.randint(4, 10)
    return " ".join(random.choices(WORDS, k=n)).capitalize() + f" {rnd(TABLES)} in {rnd(CITIES)}."


def main():
    lines = list(FACTS) * 6
    makers = [sql_line, json_line, mongo_line, schema_line, question_line]
    for _ in range(4000):
        lines.append(rnd(makers)())
    random.shuffle(lines)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {len(lines)} lines to {OUT} ({OUT.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()

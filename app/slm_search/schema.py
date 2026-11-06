"""Schema objects + ONE compact text format, shared by data generation, validation and the API.

Text format (one line):
  sql | allowed: customers, orders | customers(id int pk, name text, city text) ; orders(id int pk, customer_id int fk customers.id, total float)
  mongo | allowed: products | products(product_id int, name text, price float)

Types: int, float, text, date, bool.
"""
import re
from dataclasses import dataclass, field
from typing import Optional

TYPES = ("int", "float", "text", "date", "bool")
IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass
class Column:
    name: str
    type: str
    pk: bool = False
    fk: Optional[tuple] = None                      # (table, column)
    words: list = field(default_factory=list, compare=False)  # human words (question writing only)


@dataclass
class Table:
    name: str
    columns: list
    words: list = field(default_factory=list, compare=False)

    def column(self, name):
        for c in self.columns:
            if c.name == name:
                return c
        return None


@dataclass
class Schema:
    dialect: str                                   # "sql" or "mongo"
    tables: list
    allowed: list                                  # names of tables the current user may read
    domain: str = field(default="", compare=False)  # generator metadata, not serialized
    style: str = field(default="snake", compare=False)  # naming style (generator metadata)

    def table(self, name):
        for t in self.tables:
            if t.name == name:
                return t
        return None

    def is_allowed(self, name):
        return name in self.allowed

    def fk_edge(self, a, b):
        """Return (a_col, b_col) if table a has a foreign key pointing to table b."""
        ta = self.table(a)
        if ta:
            for c in ta.columns:
                if c.fk and c.fk[0] == b:
                    return c.name, c.fk[1]
        return None

    # ---- serialization -------------------------------------------------
    def tables_text(self):
        parts = []
        for t in self.tables:
            cols = []
            for c in t.columns:
                s = f"{c.name} {c.type}"
                if c.pk:
                    s += " pk"
                if c.fk:
                    s += f" fk {c.fk[0]}.{c.fk[1]}"
                cols.append(s)
            parts.append(f"{t.name}({', '.join(cols)})")
        return " ; ".join(parts)

    def to_text(self):
        return f"{self.dialect} | allowed: {', '.join(self.allowed)} | {self.tables_text()}"

    @staticmethod
    def from_text(text):
        head, allowed_part, tables_part = [p.strip() for p in text.split(" | ", 2)]
        if not allowed_part.startswith("allowed:"):
            raise ValueError("schema text must contain 'allowed:'")
        allowed = [a.strip() for a in allowed_part[len("allowed:"):].split(",") if a.strip()]
        tables = []
        for chunk in tables_part.split(" ; "):
            m = re.fullmatch(r"(\w+)\((.*)\)", chunk.strip())
            if not m:
                raise ValueError(f"bad table chunk: {chunk!r}")
            cols = []
            for spec in m.group(2).split(", "):
                bits = spec.split()
                col = Column(bits[0], bits[1])
                rest = bits[2:]
                if rest[:1] == ["pk"]:
                    col.pk = True
                    rest = rest[1:]
                if rest[:1] == ["fk"]:
                    t, c = rest[1].split(".")
                    col.fk = (t, c)
                cols.append(col)
            tables.append(Table(m.group(1), cols))
        return Schema(head, tables, allowed)

"""Random schema generator (2-8 tables, 3-12 columns, mixed naming styles, allowed-table list)."""
import random

from app.slm_search.schema import Column, Schema, Table
from datagen.catalog import GENERIC_COLUMNS, RESTRICTED_TABLES
from datagen.naming import STYLES, render_name, singular

TYPE_FIX = {"real": "float"}


def parse_cols(spec):
    out = []
    for item in spec.split(","):
        words, typ = item.strip().rsplit(":", 1)
        out.append((words.split(), TYPE_FIX.get(typ, typ)))
    return out


def pick_tables(rng, domains, names):
    """Choose a domain (sometimes two merged) and a connected-ish subset of 2..8 tables."""
    chosen = [rng.choice(names)]
    if rng.random() < 0.15:
        other = rng.choice([n for n in names if n != chosen[0]])
        chosen.append(other)
    tables, fks = {}, []
    for d in chosen:
        tables.update(domains[d]["tables"])
        fks += domains[d]["fks"]
    allnames = list(tables)
    max_k = min(8, len(allnames))
    r = rng.random()
    k = 2 + int(r * r * (max_k - 1)) if max_k > 2 else 2   # biased toward smaller schemas
    k = max(2, min(k, max_k))
    # grow a subset by following foreign keys so joins remain possible
    keep = [rng.choice(allnames)]
    while len(keep) < k:
        linked = [b for a, b in fks if a in keep and b not in keep] + [a for a, b in fks if b in keep and a not in keep]
        pool = linked if linked and rng.random() < 0.85 else [t for t in allnames if t not in keep]
        keep.append(rng.choice(pool))
    return "+".join(chosen), {t: tables[t] for t in keep}, [(a, b) for a, b in fks if a in keep and b in keep]


def random_schema(rng: random.Random, domains: dict, dialect: str = "sql") -> Schema:
    dom_name, tables, fks = pick_tables(rng, domains, list(domains))
    style = rng.choices(STYLES, weights=[40, 20, 20, 20])[0]
    pk_prefixed = rng.random() < 0.35
    singular_names = {t: rng.random() < 0.25 for t in tables}   # messy: some tables are singular
    def tab_words_sing(t):
        w = t.split()
        return w[:-1] + [singular(w[-1])]

    tab_words = {t: (tab_words_sing(t) if singular_names[t] else t.split()) for t in tables}
    pk_name_words = {t: (tab_words_sing(t) + ["id"]) if pk_prefixed else ["id"] for t in tables}

    built = []
    for t, spec in tables.items():
        cols, used = [], set()

        def add(words, typ, pk=False, fk=None):
            name = render_name(words, style)
            if name.lower() in used:
                return
            used.add(name.lower())
            cols.append(Column(name, typ, pk, fk, list(words)))

        add(pk_name_words[t], "int", pk=True)
        for child, parent in fks:
            if child == t:
                pw = pk_name_words[parent]
                add(tab_words_sing(parent) + ["id"], "int", fk=(render_name(tab_words[parent], style),
                                                              render_name(pw, style)))
        data = parse_cols(spec) + parse_cols(rng.choice(GENERIC_COLUMNS)) * (rng.random() < 0.4)
        rng.shuffle(data)
        room = 12 - len(cols)
        want_total = rng.randint(3, 12)
        n_data = max(1, min(room, want_total - len(cols), len(data)))
        for words, typ in data[:n_data]:
            add(words, typ)
        while len(cols) < 3 and data:                       # guarantee >= 3 columns
            words, typ = data.pop()
            add(words, typ)
        if rng.random() < 0.8:                              # keep pk near the front usually
            cols.sort(key=lambda c: (not c.pk, ))
        else:
            rng.shuffle(cols)
        built.append(Table(render_name(tab_words[t], style), cols, tab_words[t]))

    # restricted extra table (exists in the schema but the user may NOT read it)
    allowed = [t.name for t in built]
    if len(built) < 8 and rng.random() < 0.35:
        rw = rng.choice(RESTRICTED_TABLES).split()
        name = render_name(rw, style)
        if name.lower() not in {t.name.lower() for t in built}:
            pkw = ["id"]
            cols = [Column(render_name(pkw, style), "int", True, None, pkw),
                    Column(render_name(["secret", "value"], style), "text", False, None, ["secret", "value"]),
                    Column(render_name(["created", "at"], style), "date", False, None, ["created", "at"])]
            built.append(Table(name, cols, rw))
    elif len(built) >= 3 and rng.random() < 0.15:           # or revoke one normal table
        victim = rng.choice(built[1:])
        allowed.remove(victim.name)
    rng.shuffle(built)
    if dialect == "mongo":
        for t in built:
            for c in t.columns:
                c.pk, c.fk = False, None
    return Schema(dialect, built, allowed, dom_name, style)


def fingerprint(schema: Schema) -> str:
    return schema.dialect + "|" + schema.tables_text()

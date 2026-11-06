"""Naming styles + tiny English helpers (messy real-world names)."""

# Abbreviations used in the "abbr" style (cust_id, qty ...)
ABBR = {"customer": "cust", "quantity": "qty", "number": "no", "amount": "amt", "description": "desc",
        "address": "addr", "department": "dept", "employee": "emp", "product": "prod", "category": "cat",
        "telephone": "tel", "phone": "ph", "balance": "bal", "total": "tot", "price": "prc", "date": "dt",
        "status": "sts", "country": "cntry", "salary": "sal", "student": "stu", "patient": "pat",
        "order": "ord", "account": "acct", "transaction": "txn", "created": "crt", "updated": "upd",
        "message": "msg", "average": "avg", "maximum": "max", "minimum": "min", "year": "yr"}
STYLES = ["snake", "camel", "pascal", "abbr"]


def singular(word):
    if word.endswith("ies") and len(word) > 4:
        return word[:-3] + "y"
    if word.endswith(("sses", "ches", "shes", "xes")):
        return word[:-2]
    if word.endswith("s") and not word.endswith(("ss", "us", "is")):
        return word[:-1]
    return word


def plural(word):
    if word.endswith("y") and word[-2:-1] not in "aeiou":
        return word[:-1] + "ies"
    if word.endswith(("s", "x", "ch", "sh")):
        return word + "es"
    return word + "s"


def render_name(words, style):
    """['order','items'] -> order_items / orderItems / OrderItems / ord_items."""
    if style == "abbr":
        words = [ABBR.get(w, w) for w in words]
    if style in ("snake", "abbr"):
        return "_".join(words)
    if style == "pascal":
        return "".join(w.capitalize() for w in words)
    return words[0] + "".join(w.capitalize() for w in words[1:])  # camel

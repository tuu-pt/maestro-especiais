"""Activation rules of the blocks (SPEC 7.3, 8.3): a small language, parsed and evaluated here.

No eval, no Python: a recursive-descent parser turns the text into a JSON tree, which is what is
stored next to the text and evaluated. Errors say where (character position) and why, in
Portuguese, for the curator.

    rule     := or
    or       := and ("or" and)*
    and      := not ("and" not)*
    not      := "not" not | primary
    primary  := "(" rule ")" | "true" | "false" | any | test
    any      := "any" ("circuit" | "bom") "." field op literal
    test     := key ".present" | key op literal
    op       := "==" | "!=" | "~" | "in" | ">" | "<" | ">=" | "<="
    literal  := string | number | "[" literal ("," literal)* "]"

- `<key>.present`: the ficha has a value for the key, or an MQT/LPU article is linked to it.
- `<key> op literal`: compares the value of the key in the ficha. Text is compared without case
  or accents; `~` means "contains"; `in` means "is one of". With no value, a test is false.
- `any circuit.<field> …`: some circuit of the Tabela de Cálculo; `any bom.<designation|chapter|
  unit> …`: some article of the MQT/LPU (chapter = the chapter the article is in).

Nothing is computed: the rules only compare values that are already in the ficha-base.
"""

import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

from app.ingest.detect import fold
from app.ingest.keys import KEYS

OPS = ("==", "!=", ">=", "<=", "~", ">", "<", "in")
CIRCUIT_FIELDS = (
    "origin", "destination", "voltage_v", "kva", "protection_type", "ib_a", "in_a", "iz_a",
    "i2_a", "iz145_a", "cable_raw", "section_mm2", "length_m", "vd_section_pct", "vd_total_pct",
    "breaking_capacity_ka", "pole_type", "installation", "phases", "insulation", "conductor",
    "ref_method",
)  # fmt: skip
BOM_FIELDS = ("designation", "chapter", "unit")
_TOKEN = re.compile(
    r"\s*(?:(?P<string>\"(?:[^\"\\]|\\.)*\")|(?P<number>-?\d+(?:[.,]\d+)?)"
    r"|(?P<op>==|!=|>=|<=|~|>|<)|(?P<punct>[()\[\],])|(?P<name>[A-Za-z_][A-Za-z0-9_.]*))"
)


class RuleError(ValueError):
    def __init__(self, message: str, position: int) -> None:
        super().__init__(f"{message} (posição {position + 1})")
        self.message = message
        self.position = position


@dataclass(frozen=True)
class Token:
    kind: str  # string | number | op | punct | name | end
    value: str
    position: int


def tokens(text: str) -> list[Token]:
    out: list[Token] = []
    pos = 0
    while pos < len(text):
        if text[pos:].strip() == "":
            break
        m = _TOKEN.match(text, pos)
        if m is None or m.end() == pos:
            start = pos + (len(text[pos:]) - len(text[pos:].lstrip()))
            raise RuleError(f"Carácter inesperado «{text[start]}»", start)
        kind = m.lastgroup or ""
        start = m.start(kind)
        value = m.group(kind)
        if kind == "name" and value in ("in",):
            kind = "op"
        out.append(Token(kind, value, start))
        pos = m.end()
    out.append(Token("end", "", len(text)))
    return out


class _Parser:
    def __init__(self, text: str) -> None:
        self.tokens = tokens(text)
        self.i = 0

    @property
    def token(self) -> Token:
        return self.tokens[self.i]

    def take(self, kind: str | None = None, value: str | None = None) -> Token:
        t = self.token
        if (kind and t.kind != kind) or (value is not None and t.value != value):
            expected = (
                f"«{value}»"
                if value
                else {"name": "um nome", "end": "o fim"}.get(kind or "", kind or "algo")
            )
            found = f"«{t.value}»" if t.value else "o fim da regra"
            raise RuleError(f"Esperava {expected}, encontrei {found}", t.position)
        self.i += 1
        return t

    def at(self, kind: str, value: str | None = None) -> bool:
        return self.token.kind == kind and (value is None or self.token.value == value)

    def rule(self) -> dict[str, Any]:
        tree = self.or_()
        self.take("end")
        return tree

    def or_(self) -> dict[str, Any]:
        args = [self.and_()]
        while self.at("name", "or"):
            self.take()
            args.append(self.and_())
        return args[0] if len(args) == 1 else {"op": "or", "args": args}

    def and_(self) -> dict[str, Any]:
        args = [self.not_()]
        while self.at("name", "and"):
            self.take()
            args.append(self.not_())
        return args[0] if len(args) == 1 else {"op": "and", "args": args}

    def not_(self) -> dict[str, Any]:
        if self.at("name", "not"):
            self.take()
            return {"op": "not", "arg": self.not_()}
        return self.primary()

    def primary(self) -> dict[str, Any]:
        t = self.token
        if self.at("punct", "("):
            self.take()
            tree = self.or_()
            self.take("punct", ")")
            return tree
        if self.at("name", "true") or self.at("name", "false"):
            self.take()
            return {"op": "const", "value": t.value == "true"}
        if self.at("name", "any"):
            self.take()
            path = self.take("name")
            collection, _, field_ = path.value.partition(".")
            allowed = {"circuit": CIRCUIT_FIELDS, "bom": BOM_FIELDS}.get(collection)
            if allowed is None:
                raise RuleError(f"«any» só se aplica a circuit ou bom, não a «{collection}»",
                                path.position)  # fmt: skip
            if field_ not in allowed:
                raise RuleError(f"Campo desconhecido «{field_}» em {collection}", path.position)
            cmp, value = self.comparison()
            return {"op": "any", "collection": collection, "field": field_, "cmp": cmp,
                    "value": value}  # fmt: skip
        if t.kind == "name":
            self.take()
            if t.value.endswith(".present"):
                key = t.value.removesuffix(".present")
                self.known(key, t.position)
                return {"op": "present", "key": key}
            self.known(t.value, t.position)
            if not self.at("op"):
                raise RuleError(f"Falta a comparação depois de «{t.value}» (ou «.present»)",
                                self.token.position)  # fmt: skip
            cmp, value = self.comparison()
            return {"op": "cmp", "key": t.value, "cmp": cmp, "value": value}
        found = f"«{t.value}»" if t.value else "o fim da regra"
        raise RuleError(f"Esperava uma condição, encontrei {found}", t.position)

    def known(self, key: str, position: int) -> None:
        if key not in KEYS:
            raise RuleError(f"Chave desconhecida «{key}»", position)

    def comparison(self) -> tuple[str, Any]:
        op = self.take("op")
        value = self.literal()
        if op.value == "in" and not isinstance(value, list):
            raise RuleError('Depois de «in» vem uma lista: ["a", "b"]', op.position)
        return op.value, value

    def literal(self) -> Any:
        t = self.token
        if t.kind == "string":
            self.take()
            return re.sub(r"\\(.)", r"\1", t.value[1:-1])
        if t.kind == "number":
            self.take()
            return float(t.value.replace(",", "."))
        if self.at("punct", "["):
            self.take()
            items = [self.literal()]
            while self.at("punct", ","):
                self.take()
                items.append(self.literal())
            self.take("punct", "]")
            return items
        found = f"«{t.value}»" if t.value else "o fim da regra"
        what = "um valor (texto entre aspas, número ou lista)"
        raise RuleError(f"Esperava {what}, encontrei {found}", t.position)


def parse(text: str) -> dict[str, Any]:
    """The tree of a rule. Raises RuleError with the position of the problem."""
    if not text.strip():
        raise RuleError("A regra está vazia", 0)
    return _Parser(text).rule()


# ---------------------------------------------------------------- evaluation


@dataclass
class Context:
    """What a rule can see of a project: ficha values, linked articles, circuits and articles."""

    values: dict[str, Any] = field(default_factory=dict)
    linked: set[str] = field(default_factory=set)  # keys with an MQT/LPU article linked
    circuits: list[dict[str, Any]] = field(default_factory=list)
    bom: list[dict[str, Any]] = field(default_factory=list)  # designation, chapter, unit


def _number(value: Any) -> Decimal | None:
    if isinstance(value, bool):
        return None
    try:
        return Decimal(str(value).replace(",", "."))
    except (InvalidOperation, ValueError):
        return None


def _compare(actual: Any, cmp: str, expected: Any) -> bool:
    if actual in (None, ""):
        return False
    if cmp == "in":
        return any(_compare(actual, "==", item) for item in expected)
    if cmp == "~":
        return fold(expected) in fold(actual)
    a, b = _number(actual), _number(expected)
    if a is not None and b is not None:
        return {"==": a == b, "!=": a != b, ">": a > b, "<": a < b, ">=": a >= b,
                "<=": a <= b}[cmp]  # fmt: skip
    if cmp in ("==", "!="):
        return (fold(actual) == fold(expected)) == (cmp == "==")
    return False  # order between texts is not a rule


def evaluate(tree: dict[str, Any], ctx: Context) -> bool:
    op = tree["op"]
    if op == "const":
        return bool(tree["value"])
    if op == "not":
        return not evaluate(tree["arg"], ctx)
    if op == "and":
        return all(evaluate(a, ctx) for a in tree["args"])
    if op == "or":
        return any(evaluate(a, ctx) for a in tree["args"])
    if op == "present":
        value = ctx.values.get(tree["key"])
        return value not in (None, "", [], {}) or tree["key"] in ctx.linked
    if op == "cmp":
        return _compare(ctx.values.get(tree["key"]), tree["cmp"], tree["value"])
    if op == "any":
        rows = ctx.circuits if tree["collection"] == "circuit" else ctx.bom
        return any(_compare(r.get(tree["field"]), tree["cmp"], tree["value"]) for r in rows)
    raise ValueError(f"unknown rule node: {op}")


def check(text: str, ctx: Context) -> bool:
    return evaluate(parse(text), ctx)

"""COE-02 (SPEC 9, P5): a source dated after the ficha-base that diverges from it.

The ficha-base is the source of truth but may be wrong: when a file is more recent than the
confirmed ficha-base and says something else, the proposal is to update the ficha (a new
revision), never the pieces. Only the ficha keys (SPEC 7.2) a file gives are compared.
"""

from app.ingest.keys import KEYS
from app.validation.compare import evidence, location, observations
from app.validation.context import Context
from app.validation.core import OPEN_FICHA, Finding, Rule
from app.validation.likely import NEWER_THAN_FICHA, newer
from app.validation.normalize import same

FILES = ("FICHA_ELE", "CALC", "MQT", "LPU", "DRAWINGS", "IDENTIFICACAO", "TERMO")
SKIP = {"ele.quadros", "ele.cabos", "pd.indice", "pd.folhas"}  # compared by COE-01/06, DES-01


def check(ctx: Context) -> list[Finding]:
    out = []
    for piece in ctx.of_kind(*FILES):
        if not newer(piece, ctx.ficha_date):
            continue
        keys = {f.key for f in ctx.data[piece.ref].facts if f.key in KEYS and f.key not in SKIP}
        for key in sorted(keys):
            ref = ctx.ficha_value(key)
            obs = observations(ctx, key, [piece.kind])
            if ref is None or not obs or same(obs[0].fact.value, ref):
                continue
            personal = KEYS[key].personal
            out.append(RULE.finding(
                f"{piece.name} (de {piece.date}) é posterior à ficha-base (confirmada a "
                f"{ctx.ficha_date}) e diverge em «{KEYS[key].label_pt}».",
                key=f"{piece.ref}|{key}", location=location(piece, obs[0].fact),
                evidence=evidence(ctx, ref, "ficha-base", obs, obs, personal=personal),
                likely_reading=NEWER_THAN_FICHA.format(name=piece.name),
                suggested_fix="Abrir uma nova revisão da ficha-base com o valor da fonte "
                "mais recente, depois de confirmado.",
                actions=[OPEN_FICHA],
            ))  # fmt: skip
    return out


RULE = Rule("COE-02", "coherence", "warning", "Fonte mais recente do que a ficha-base", check)

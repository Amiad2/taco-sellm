"""Check cited data offline, by the arena's published rules (docs/CONTEXT.md section 7).

Each sentence is one argument: the data IDs in it and the figure written next to them. Results are
`verified`, `irrelevant` (true but not about this supplier or part, or an index window too long or
too old), `contradicted` (unknown ID or wrong figure) or `duplicate` (the ID was used before in
this case; a quote or offer once per supplier). At most 3 results per message.

The lab's suppliers use this; our own agent can use it to check a sentence before sending it.
"""

import re

ID_RE = re.compile(r"\b(?:idx|quote|offer|sc|qn|po|cost|fc|news|doc|ctr):[\w.:@#/-]*\w")
CONTEXT_ONLY = ("sup:", "part:", "rfq:", "gr:", "inv:")  # context, never checked
SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z(\"'])|\n+")
NUMBER = r"[+\-−–]?\d{1,3}(?:[,\s]\d{3})*(?:\.\d+)?|[+\-−–]?\d+(?:[.,]\d+)?"
PCT = re.compile(rf"({NUMBER})\s?(?:%|per ?cent|percent)", re.I)
EUR = re.compile(rf"(?:€|EUR)\s?({NUMBER})|({NUMBER})\s?(?:€|EUR\b|euros?\b)", re.I)
PPM = re.compile(rf"({NUMBER})\s?ppm", re.I)
DAYS = re.compile(r"(\d+)\s?(?:calendar\s)?days?", re.I)
FALL = re.compile(
    r"\b(fell|fall(?:en|ing)?|drop(?:ped|s)?|declin(?:ed|e|ing)|decreas(?:ed|e)|down|lower(?:ed)?)\b", re.I
)
QUALITY = re.compile(r"\b(ppm|defect|quality|complaint|reject)", re.I)
MAX_RESULTS = 3


def _num(text):
    t = text.replace("−", "-").replace("–", "-").replace(" ", "")
    if re.fullmatch(r"[+-]?\d{1,3}(,\d{3})+(\.\d+)?", t):
        t = t.replace(",", "")
    else:
        t = t.replace(",", ".")
    return float(t)


def _close(ours, theirs, pct=False):
    if ours is None:
        return True  # without a figure the data's own value is taken
    if pct:
        return abs(ours - theirs) <= 0.5
    return abs(ours - theirs) <= max(0.01, abs(theirs) * 0.005)


def _months(a, b):
    ya, ma = map(int, a.split("-"))
    yb, mb = map(int, b.split("-"))
    return (yb - ya) * 12 + (mb - ma)


class ClaimChecker:
    def __init__(self, facts, case, drivers=None):
        """`facts`: the package's facts.json (plus the case's own `facts`). `drivers`: index series
        that bear on the case's parts (cost_drivers), so an index claim can be relevant."""
        self.facts = {**facts, **case.get("facts", {})}
        self.case, self.parts = case, set(case.get("parts", []))
        self.series = set(drivers or [])
        for opt in case.get("term_options", {}).get("index_clause", []) or []:
            if opt:
                self.series.add(opt["series"])
        self.series |= set(case.get("buyer", {}).get("index_paths", {}))
        self.last_month = {}
        for k, v in self.facts.items():
            if k.startswith("idx:"):
                s = v["series"]
                self.last_month[s] = max(self.last_month.get(s, ""), v["month"])

    def claims(self, body, refs=()):
        """[(ids, text)] in the order written; refs not named in the body come last, alone. A
        letter and a contract form one argument across the whole e-mail (the notice it gives)."""
        out, named, letter = [], set(), None
        for sentence in SENTENCE.split(body or ""):
            ids = [i for i in dict.fromkeys(ID_RE.findall(sentence)) if not i.startswith(CONTEXT_ONLY)]
            named |= set(ids)
            groups = {}
            for i in ids:
                kind = i.split(":", 1)[0]
                if kind in ("doc", "ctr"):
                    if letter is None:
                        letter = ([], [])
                        out.append(letter)
                    if i not in letter[0]:
                        letter[0].append(i)
                    letter[1].append(sentence)
                    continue
                groups.setdefault(kind if kind in ("idx", "po") else i, []).append(i)
            out += [(g, sentence) for g in groups.values()]
        out = [(ids, " ".join(text) if isinstance(text, list) else text) for ids, text in out]
        out += [([r], "") for r in dict.fromkeys(refs or []) if r not in named and not r.startswith(CONTEXT_ONLY)]
        return out

    def check(self, supplier_id, body, refs=(), offers=None, used=None):
        """Results for one message: [{"index", "result", "ids", "kind"}]. `offers`: {offer_id: (supplier,
        terms)} made in this session. `used`: the case's set of keys already cited (updated)."""
        offers, used = offers or {}, used if used is not None else set()
        results = []
        for ids, sentence in self.claims(body, refs):
            if len(results) == MAX_RESULTS:
                break
            kind = ids[0].split(":", 1)[0]
            if kind == "ctr" and len(ids) == 1:
                continue  # a contract alone is context
            keys = [(supplier_id, i) if i.startswith(("quote:", "offer:")) else i for i in ids]
            known = all(i in self.facts or i in offers for i in ids)
            if not known:
                result = "contradicted"
            elif any(k in used for k in keys):
                result = "duplicate"
            else:
                try:
                    result = self._judge(kind, ids, sentence, supplier_id, offers)
                except (KeyError, TypeError, ValueError, ZeroDivisionError):
                    result = "irrelevant"
            if known:
                used.update(keys)
            results.append({"index": len(results), "result": result, "ids": ids, "kind": kind})
        return results

    def _judge(self, kind, ids, sentence, sup, offers):
        f = self.facts
        pct = [_num(m) for m in PCT.findall(sentence)]
        eur = [_num(a or b) for a, b in EUR.findall(sentence)]
        ppm = [_num(m) for m in PPM.findall(sentence)]

        def nearest(cands, true):
            return min(cands, key=lambda x: abs(x - true)) if cands else None

        if kind == "idx":
            rows = sorted((f[i] for i in ids), key=lambda r: r["month"])
            if len({r["series"] for r in rows}) != 1:
                return "irrelevant"
            series = rows[0]["series"]
            if len(rows) < 2:
                return "verified" if series in self.series else "irrelevant"
            a, b = rows[0], rows[-1]
            if _months(a["month"], b["month"]) > 12 or _months(b["month"], self.last_month[series]) > 12:
                return "irrelevant"
            change = (b["value"] / a["value"] - 1) * 100
            if pct and FALL.search(sentence):
                pct = [-abs(x) for x in pct]
            ok = _close(nearest(pct, change), change, pct=True)
            return "contradicted" if not ok else "verified" if series in self.series else "irrelevant"
        if kind in ("quote", "offer"):
            i = ids[0]
            if kind == "offer":
                owner, terms = offers[i]
                part_ok, price = owner != sup, terms.get("unit_price")
            else:
                part_ok, price = f[i]["part"] in self.parts, f[i]["unit_price"]
            if not _close(nearest(eur, price), price):
                return "contradicted"
            return "verified" if part_ok else "irrelevant"
        if kind in ("sc", "qn"):
            rows = [f[i] for i in ids]
            if any(r["supplier"] != sup for r in rows):
                return "irrelevant"
            if kind == "qn" or (ppm and QUALITY.search(sentence)):
                true = sum(r["ppm"] for r in rows) / len(rows)
                return "verified" if _close(nearest(ppm or pct, true), true) else "contradicted"
            true = sum(r["otd_pct"] for r in rows) / len(rows)
            return "verified" if _close(nearest(pct, true), true, pct=True) else "contradicted"
        if kind == "po":
            rows = [f[i] for i in ids]
            if not 2 <= len(rows) <= 8 or len({r["part"] for r in rows}) != 1:
                return "irrelevant"
            return "verified" if rows[0]["supplier"] == sup and rows[0]["part"] in self.parts else "irrelevant"
        if kind == "fc":
            r = f[ids[0]]
            if r["part"] not in self.parts:
                return "irrelevant"
            return "verified" if _close(nearest(pct, r["change_pct"]), r["change_pct"], pct=True) else "contradicted"
        if kind == "cost":
            r = f[ids[0]]
            if r["part"] not in self.parts:
                return "irrelevant"
            return "verified" if _close(nearest(eur, r["unit_cost"]), r["unit_cost"]) else "contradicted"
        if kind == "news":
            return "verified" if f[ids[0]].get("supplier") == sup else "irrelevant"
        if kind in ("doc", "ctr"):
            rows = [f[i] for i in ids]
            if any(r.get("supplier") != sup for r in rows):
                return "irrelevant"
            days = [int(d) for d in DAYS.findall(sentence)]
            truth = [r["days"] for r in rows if r.get("days")]
            return "verified" if not days or any(d in truth for d in days) else "contradicted"
        return "irrelevant"

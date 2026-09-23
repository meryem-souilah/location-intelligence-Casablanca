"""Référentiel des marques bancaires (données de référence / master data).

OSM contient des dizaines d'écritures pour une même banque : « Attijariwafa Bank »,
« التجاري وفا بنك », « Attijarlwafa Bank », « wafa bank »... Chaque objet est
rattaché à une marque canonique en testant les motifs ci-dessous, dans l'ordre,
sur la concaténation brand | name | operator | name:fr.

L'ordre compte : les non-banques sont écartées en premier (WafaCash n'est pas
Attijariwafa bank), puis les motifs les plus spécifiques passent avant les plus
larges (BMCI avant « banque »).
"""
import re

from .utils import normalize_text

# Établissements qui ne sont pas des agences bancaires de détail : exclus de la
# concurrence (sociétés de transfert, crédit conso, assurance, banque centrale).
NON_BANQUES = [
    r"wafa ?cash", r"western union", r"exchange", r"bureau de change", r"\baxa\b",
    r"salaf", r"wafa immobilier", r"barid ?cash", r"baird cash", r"\bcima\b",
    r"tresorerie", r"الخزينة", r"bank al.?maghrib", r"money ?gram", r"damane cash",
    r"cash plus", r"\bria\b",
]

MARQUES = [
    ("Bank of Africa", [r"bank of africa", r"\bbmce\b", r"b m c e", r"بنك افريقيا", r"بنك أفريقيا"]),
    ("BMCI", [r"\bbmci\b", r"البنك المغربي للتجارة", r"banque marocaine pour le commerce"]),
    ("Banque Populaire", [r"populaire", r"popular", r"populare", r"chaabi", r"الشعبي", r"\bbcp\b"]),
    ("Attijariwafa bank", [r"atti", r"wafa ?ban", r"التجاري"]),
    ("Saham Bank", [r"saham", r"سهام", r"societe generale", r"\bsgma?b?\b"]),
    ("Crédit du Maroc", [r"credit du maroc", r"مصرف المغرب"]),
    ("CIH Bank", [r"\bcih\b", r"\bch bank\b", r"القرض العقاري", r"credit immobilier et hotelier"]),
    ("Crédit Agricole du Maroc", [r"credit agricole", r"القرض الفلاحي"]),
    ("Al Barid Bank", [r"barid", r"البريد"]),
    ("CFG Bank", [r"\bcfg\b"]),
    ("Umnia Bank", [r"umnia", r"امنية"]),
    ("Bank Assafa", [r"assafa", r"الصفاء"]),
    ("Bank Al Yousr", [r"yousr", r"اليسر"]),
    ("Dar Al Amane", [r"dar al amane", r"دار الامان"]),
    ("Al Akhdar Bank", [r"akhdar", r"الاخضر"]),
    ("BTI Bank", [r"\bbti\b"]),
    ("Arab Bank", [r"arab bank"]),
    ("Autres banques", [r"caixa", r"\bcic\b", r"citibank", r"\bcdg\b"]),
]

NON_IDENTIFIEE = "Non identifiée"
NON_BANQUE = "Hors périmètre (non-banque)"

_NON_BANQUES = [re.compile(normalize_text(p)) for p in NON_BANQUES]
_MARQUES = [(m, [re.compile(normalize_text(p)) for p in ps]) for m, ps in MARQUES]


def canonical_brand(*labels) -> str:
    """Retourne la marque canonique d'un objet OSM à partir de ses libellés."""
    text = " | ".join(normalize_text(x) for x in labels if normalize_text(x))
    if not text:
        return NON_IDENTIFIEE
    if any(p.search(text) for p in _NON_BANQUES):
        return NON_BANQUE
    for marque, motifs in _MARQUES:
        if any(p.search(text) for p in motifs):
            return marque
    return NON_IDENTIFIEE

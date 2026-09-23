"""Exécute le pipeline complet : Bronze -> Silver -> Gold -> cartes.

    python run_pipeline.py                 # tout
    python run_pipeline.py --from scoring  # reprend à une étape (ex. après avoir changé les poids)
"""
import argparse
import time

from locintel import clean, export, huff, indicators, ingest, maps, powerbi, quality, scoring, web
from locintel.utils import log, setup

STEPS = [("ingest", ingest), ("clean", clean), ("indicators", indicators), ("scoring", scoring),
         ("huff", huff), ("quality", quality), ("export", export), ("maps", maps),
         ("powerbi", powerbi), ("web", web)]

if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--from", dest="start", choices=[s for s, _ in STEPS], default="ingest")
    p.add_argument("--only", choices=[s for s, _ in STEPS])
    a = p.parse_args()
    setup()
    names = [s for s, _ in STEPS]
    todo = [a.only] if a.only else names[names.index(a.start):]
    for name, mod in STEPS:
        if name in todo:
            t = time.time()
            log.info("=== %s ===", name.upper())
            mod.run()
            log.info("    %s terminé en %.1f s", name, time.time() - t)

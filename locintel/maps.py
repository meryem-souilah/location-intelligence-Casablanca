"""Étape 8 — Cartes statiques (README, deck de restitution).

Couleurs : rampe séquentielle bleue pour les magnitudes, gris neutre pour les
zones exclues, orange réservé au client. Aucune information portée par la seule
couleur : les recommandations sont aussi numérotées et cerclées.
"""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.cm import ScalarMappable  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap, Normalize  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

from . import config  # noqa: E402
from .export import ATTRIBUTION  # noqa: E402
from .utils import log, read  # noqa: E402

BLUES = LinearSegmentedColormap.from_list(
    "blues", ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"])
INK, INK2, MUTED, GRID = "#0b0b0b", "#52514e", "#898781", "#c3c2b7"
EXCLU, CLIENT, CONCURRENT = "#e1e0d9", "#eb6834", "#52514e"


def _base(ax, arr, title, subtitle):
    arr.boundary.plot(ax=ax, color=GRID, linewidth=0.6, zorder=3)
    ax.set_axis_off()
    ax.set_title(title, loc="left", fontsize=14, color=INK, fontweight="bold", pad=22)
    ax.text(0, 1.015, subtitle, transform=ax.transAxes, fontsize=9.5, color=INK2)
    ax.text(0, -0.02, ATTRIBUTION, transform=ax.transAxes, fontsize=7, color=MUTED, va="top")


def _colorbar(fig, ax, mappable, label):
    cb = fig.colorbar(mappable, ax=ax, shrink=0.5, pad=0.01)
    cb.outline.set_visible(False)
    cb.ax.tick_params(colors=INK2, labelsize=8, length=0)
    cb.set_label(label, color=INK2, fontsize=9)


def run():
    sc = read(config.SILVER / "scores_h3.gpkg")
    ag = read(config.SILVER / "agences.gpkg")
    ag = ag[ag["type"] == "agence"]
    arr = read(config.SILVER / "arrondissements.gpkg")
    plt.rcParams.update({"font.family": "Segoe UI", "figure.facecolor": "#fcfcfb"})

    # 1. Carte des scores et recommandations
    fig, ax = plt.subplots(figsize=(11, 9))
    sc[sc["exclu"]].plot(ax=ax, color=EXCLU, edgecolor="#fcfcfb", linewidth=0.4)
    m = sc[~sc["exclu"]].plot(ax=ax, column="score_100", cmap=BLUES, edgecolor="#fcfcfb", linewidth=0.4)
    _colorbar(fig, ax, m.collections[-1], "Score d'opportunité (0-100)")
    reco = sc[sc["recommande"]].sort_values("rang_recommandation")
    reco.boundary.plot(ax=ax, color=INK, linewidth=2.2, zorder=5)
    for _, r in reco.iterrows():
        c = r.geometry.centroid
        ax.annotate(f"{int(r['rang_recommandation'])}  {r['arrondissement']}", (c.x, c.y), xytext=(-16, 12),
                    textcoords="offset points", ha="right", fontsize=10, fontweight="bold", color=INK,
                    bbox=dict(boxstyle="round,pad=0.3", fc="#fcfcfb", ec=INK, lw=0.8), zorder=6)
    ax.legend(handles=[Patch(fc=EXCLU, label="Exclu (agence client < 500 m ou zone peu peuplée)"),
                       Patch(fc="none", ec=INK, lw=2, label="Zone recommandée")],
              loc="lower left", frameon=False, fontsize=8.5, labelcolor=INK2)
    _base(ax, arr, "Où ouvrir les 3 prochaines agences ?",
          f"Score multicritère par hexagone H3 (~0,74 km²), zones retenues après modèle de Huff"
          f" — client : {config.CLIENT_BRAND}")
    fig.savefig(config.FIGURES / "carte_score.png", dpi=150, bbox_inches="tight")
    plt.close(fig)

    # 2. Demande vs offre
    fig, ax = plt.subplots(figsize=(11, 9))
    m = sc.plot(ax=ax, column="population", cmap=BLUES, edgecolor="#fcfcfb", linewidth=0.3)
    _colorbar(fig, ax, m.collections[-1], "Habitants par hexagone")
    ag[~ag["est_client"]].plot(ax=ax, color=CONCURRENT, markersize=6, alpha=0.8, zorder=4)
    ag[ag["est_client"]].plot(ax=ax, color=CLIENT, markersize=40, edgecolor="#fcfcfb", linewidth=1,
                              marker="D", zorder=5)
    ax.legend(handles=[Line2D([], [], marker="o", ls="", color=CONCURRENT, ms=4,
                              label=f"Agence concurrente ({(~ag['est_client']).sum()})"),
                       Line2D([], [], marker="D", ls="", color=CLIENT, mec="#fcfcfb", ms=8,
                              label=f"Agence {config.CLIENT_BRAND} ({ag['est_client'].sum()})")],
              loc="lower left", frameon=False, fontsize=9, labelcolor=INK2)
    _base(ax, arr, "La population est à l'est, les agences sont au centre",
          "Population par hexagone (Kontur calé sur le RGPH 2024) et agences bancaires OpenStreetMap")
    fig.savefig(config.FIGURES / "carte_demande_offre.png", dpi=150, bbox_inches="tight")
    plt.close(fig)

    # 3. Les quatre indicateurs normalisés (petits multiples, même échelle 0-1)
    fig, axs = plt.subplots(2, 2, figsize=(13, 8.2))
    items = [("demande_norm", "Demande (population k=1)"),
             ("concurrence_norm", "Concurrence (agences à 1 km)"),
             ("accessibilite_norm", "Accessibilité (tram/busway, axes)"),
             ("attractivite_norm", "Attractivité (commerces, bureaux...)")]
    for ax, (col, t) in zip(axs.flat, items):
        sc.plot(ax=ax, column=col, cmap=BLUES, vmin=0, vmax=1, edgecolor="#fcfcfb", linewidth=0.2)
        arr.boundary.plot(ax=ax, color=GRID, linewidth=0.5)
        ax.set_axis_off()
        ax.set_title(t, loc="left", fontsize=11, color=INK)
    fig.subplots_adjust(hspace=0.08, wspace=0.02, bottom=0.1)
    cb = fig.colorbar(ScalarMappable(Normalize(0, 1), BLUES), cax=fig.add_axes([0.38, 0.07, 0.26, 0.014]),
                      orientation="horizontal")
    cb.outline.set_visible(False)
    cb.ax.tick_params(colors=INK2, labelsize=8, length=0)
    cb.set_label("Valeur normalisée (0 = faible, 1 = fort)", color=INK2, fontsize=9)
    fig.suptitle("Les quatre familles d'indicateurs", x=0.13, y=0.95, ha="left", fontsize=14, fontweight="bold", color=INK)
    fig.text(0.13, 0.015, ATTRIBUTION, fontsize=7, color=MUTED)
    fig.savefig(config.FIGURES / "indicateurs.png", dpi=130, bbox_inches="tight")
    plt.close(fig)

    # 4. Huff : clientèle captable des candidats (barres horizontales)
    h = pd.read_csv(config.SILVER / "huff_candidats.csv").sort_values("gain_net_client")
    fig, ax = plt.subplots(figsize=(10, 5.5))
    ax.set_facecolor("#fcfcfb")
    labels = [f"{a} (rang score {r})" for a, r in zip(h["arrondissement"], h["rang_score"])]
    colors = ["#256abf" if r else "#9ec5f4" for r in h["recommande"]]
    ax.barh(labels, h["gain_net_client"], color=colors, height=0.6)
    for y, (v, cap) in enumerate(zip(h["gain_net_client"], h["clients_captes"])):
        ax.text(v, y, f"  {v:,} (captés {cap:,})".replace(",", " "), va="center", fontsize=8.5, color=INK2)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=INK2, labelsize=9, length=0)
    ax.set_xlabel("Gain net de clientèle potentielle (habitants, après cannibalisation)", color=INK2, fontsize=9)
    ax.set_title("Modèle de Huff : clientèle captable par site candidat", loc="left", fontsize=13,
                 fontweight="bold", color=INK)
    ax.legend(handles=[Patch(fc="#256abf", label="Recommandé"), Patch(fc="#9ec5f4", label="Autre candidat")],
              frameon=False, fontsize=8.5, loc="lower right", labelcolor=INK2)
    ax.set_xlim(0, h["gain_net_client"].max() * 1.35)
    fig.savefig(config.FIGURES / "huff_candidats.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    log.info("Cartes enregistrées dans figures/")

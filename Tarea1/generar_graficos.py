"""
generar_graficos.py
Genera los graficos para el informe de la Tarea 1 - Sistemas Distribuidos 2026-1
Ejecutar con: python3 generar_graficos.py
Los graficos se guardan en la carpeta graficos/
"""
 
import os
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
 
os.makedirs("graficos", exist_ok=True)
 
plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 11,
    "axes.titlesize": 13,
    "axes.titleweight": "bold",
    "axes.spines.top": False,
    "axes.spines.right": False,
    "figure.dpi": 150,
})
 
AZUL   = "#2563EB"
VERDE  = "#16A34A"
ROJO   = "#DC2626"
NARANJA= "#EA580C"
MORADO = "#7C3AED"
GRIS   = "#6B7280"
 
# ---------------------------------------------------------------------------
# Datos de los experimentos
# ---------------------------------------------------------------------------
experimentos = [
    {"id": 1, "dist": "Zipf",    "mem": "200mb", "pol": "LRU",    "ttl": 60,  "hit": 89.4, "thr": 35.6, "p50": 87.6,  "p95": 1382},
    {"id": 2, "dist": "Uniform", "mem": "200mb", "pol": "LRU",    "ttl": 60,  "hit": 89.6, "thr": 37.4, "p50": 83.1,  "p95": 1213},
    {"id": 3, "dist": "Zipf",    "mem": "50mb",  "pol": "LRU",    "ttl": 60,  "hit": 89.4, "thr": 38.5, "p50": 79.6,  "p95": 1310},
    {"id": 4, "dist": "Zipf",    "mem": "500mb", "pol": "LRU",    "ttl": 60,  "hit": 89.4, "thr": 37.6, "p50": 75.8,  "p95": 1298},
    {"id": 5, "dist": "Zipf",    "mem": "200mb", "pol": "LFU",    "ttl": 60,  "hit": 89.1, "thr": 36.3, "p50": 83.9,  "p95": 1340},
    {"id": 6, "dist": "Zipf",    "mem": "200mb", "pol": "Random", "ttl": 60,  "hit": 89.4, "thr": 36.9, "p50": 81.1,  "p95": 1313},
    {"id": 7, "dist": "Zipf",    "mem": "200mb", "pol": "LRU",    "ttl": 30,  "hit": 89.4, "thr": 37.2, "p50": 81.7,  "p95": 1276},
    {"id": 8, "dist": "Zipf",    "mem": "200mb", "pol": "LRU",    "ttl": 300, "hit": 88.0, "thr": 210.8,"p50": 26.2,  "p95": 183},
]
 
 
# ---------------------------------------------------------------------------
# Grafico 1: Hit Rate por experimento
# ---------------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(10, 4.5))
ids   = [str(e["id"]) for e in experimentos]
hits  = [e["hit"] for e in experimentos]
colores = [AZUL if e["dist"]=="Zipf" else VERDE for e in experimentos]
 
bars = ax.bar(ids, hits, color=colores, width=0.6, zorder=2)
ax.axhline(y=np.mean(hits), color=ROJO, linestyle="--", linewidth=1.2, label=f"Promedio: {np.mean(hits):.1f}%")
ax.set_ylim(85, 92)
ax.set_xlabel("Experimento")
ax.set_ylabel("Hit Rate (%)")
ax.set_title("Hit Rate por experimento")
ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.1f%%"))
ax.grid(axis="y", alpha=0.3, zorder=1)
ax.legend()
 
from matplotlib.patches import Patch
leyenda = [Patch(color=AZUL, label="Zipf"), Patch(color=VERDE, label="Uniforme")]
ax.legend(handles=leyenda + [plt.Line2D([0],[0], color=ROJO, linestyle="--", label=f"Promedio {np.mean(hits):.1f}%")],
          loc="lower right")
 
for bar, val in zip(bars, hits):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.05,
            f"{val}%", ha="center", va="bottom", fontsize=9)
 
plt.tight_layout()
plt.savefig("graficos/01_hit_rate.png")
plt.close()
print("Grafico 1 guardado: graficos/01_hit_rate.png")
 
 
# ---------------------------------------------------------------------------
# Grafico 2: Zipf vs Uniforme (hit rate y latencia p50)
# ---------------------------------------------------------------------------
fig, axes = plt.subplots(1, 2, figsize=(10, 4.5))
 
dists = ["Zipf", "Uniforme"]
hit_vals = [89.4, 89.6]
p50_vals = [87.6, 83.1]
 
axes[0].bar(dists, hit_vals, color=[AZUL, VERDE], width=0.4)
axes[0].set_ylim(88, 91)
axes[0].set_ylabel("Hit Rate (%)")
axes[0].set_title("Hit Rate: Zipf vs Uniforme")
axes[0].yaxis.set_major_formatter(mticker.FormatStrFormatter("%.1f%%"))
axes[0].grid(axis="y", alpha=0.3)
for i, v in enumerate(hit_vals):
    axes[0].text(i, v + 0.05, f"{v}%", ha="center", va="bottom", fontsize=10)
 
axes[1].bar(dists, p50_vals, color=[AZUL, VERDE], width=0.4)
axes[1].set_ylabel("Latencia p50 (ms)")
axes[1].set_title("Latencia p50: Zipf vs Uniforme")
axes[1].grid(axis="y", alpha=0.3)
for i, v in enumerate(p50_vals):
    axes[1].text(i, v + 0.5, f"{v}ms", ha="center", va="bottom", fontsize=10)
 
plt.suptitle("Comparacion de distribuciones de trafico", fontweight="bold")
plt.tight_layout()
plt.savefig("graficos/02_distribucion_trafico.png")
plt.close()
print("Grafico 2 guardado: graficos/02_distribucion_trafico.png")
 
 
# ---------------------------------------------------------------------------
# Grafico 3: Impacto del tamano de cache
# ---------------------------------------------------------------------------
fig, axes = plt.subplots(1, 2, figsize=(10, 4.5))
 
mem_labels = ["50mb", "200mb", "500mb"]
hit_mem    = [89.4, 89.4, 89.4]
p50_mem    = [79.6, 87.6, 75.8]
thr_mem    = [38.5, 35.6, 37.6]
 
axes[0].plot(mem_labels, p50_mem, marker="o", color=AZUL, linewidth=2, markersize=8)
axes[0].set_ylabel("Latencia p50 (ms)")
axes[0].set_title("Latencia p50 segun tamano de cache")
axes[0].grid(alpha=0.3)
for i, v in enumerate(p50_mem):
    axes[0].annotate(f"{v}ms", (mem_labels[i], v), textcoords="offset points",
                     xytext=(0, 8), ha="center", fontsize=9)
 
axes[1].plot(mem_labels, thr_mem, marker="s", color=VERDE, linewidth=2, markersize=8)
axes[1].set_ylabel("Throughput (req/s)")
axes[1].set_title("Throughput segun tamano de cache")
axes[1].grid(alpha=0.3)
for i, v in enumerate(thr_mem):
    axes[1].annotate(f"{v}", (mem_labels[i], v), textcoords="offset points",
                     xytext=(0, 8), ha="center", fontsize=9)
 
plt.suptitle("Impacto del tamano de cache (politica LRU, TTL=60s)", fontweight="bold")
plt.tight_layout()
plt.savefig("graficos/03_tamano_cache.png")
plt.close()
print("Grafico 3 guardado: graficos/03_tamano_cache.png")
 
 
# ---------------------------------------------------------------------------
# Grafico 4: Comparacion de politicas de reemplazo
# ---------------------------------------------------------------------------
fig, axes = plt.subplots(1, 2, figsize=(10, 4.5))
 
pols      = ["LRU", "LFU", "Random"]
hit_pol   = [89.4, 89.1, 89.4]
p50_pol   = [87.6, 83.9, 81.1]
p95_pol   = [1382, 1340, 1313]
colores_pol = [AZUL, MORADO, NARANJA]
 
bars1 = axes[0].bar(pols, hit_pol, color=colores_pol, width=0.4)
axes[0].set_ylim(88, 91)
axes[0].set_ylabel("Hit Rate (%)")
axes[0].set_title("Hit Rate por politica")
axes[0].yaxis.set_major_formatter(mticker.FormatStrFormatter("%.1f%%"))
axes[0].grid(axis="y", alpha=0.3)
for bar, v in zip(bars1, hit_pol):
    axes[0].text(bar.get_x() + bar.get_width()/2, v + 0.05,
                 f"{v}%", ha="center", va="bottom", fontsize=9)
 
x = np.arange(len(pols))
w = 0.35
bars_p50 = axes[1].bar(x - w/2, p50_pol, w, label="p50", color=colores_pol, alpha=0.9)
bars_p95 = axes[1].bar(x + w/2, [v/10 for v in p95_pol], w, label="p95 / 10", color=colores_pol, alpha=0.4)
axes[1].set_xticks(x)
axes[1].set_xticklabels(pols)
axes[1].set_ylabel("Latencia (ms)")
axes[1].set_title("Latencia p50 y p95/10 por politica")
axes[1].legend()
axes[1].grid(axis="y", alpha=0.3)
 
plt.suptitle("Comparacion de politicas de reemplazo (200mb, TTL=60s)", fontweight="bold")
plt.tight_layout()
plt.savefig("graficos/04_politicas_reemplazo.png")
plt.close()
print("Grafico 4 guardado: graficos/04_politicas_reemplazo.png")
 
 
# ---------------------------------------------------------------------------
# Grafico 5: Impacto del TTL
# ---------------------------------------------------------------------------
fig, axes = plt.subplots(1, 2, figsize=(10, 4.5))
 
ttls     = [30, 60, 300]
hit_ttl  = [89.4, 89.4, 88.0]
p50_ttl  = [81.7, 87.6, 26.2]
thr_ttl  = [37.2, 35.6, 210.8]
 
axes[0].plot(ttls, p50_ttl, marker="o", color=AZUL, linewidth=2, markersize=8)
axes[0].set_xlabel("TTL (segundos)")
axes[0].set_ylabel("Latencia p50 (ms)")
axes[0].set_title("Latencia p50 segun TTL")
axes[0].set_xscale("log")
axes[0].grid(alpha=0.3)
for i, (t, v) in enumerate(zip(ttls, p50_ttl)):
    axes[0].annotate(f"{v}ms", (t, v), textcoords="offset points",
                     xytext=(5, 5), fontsize=9)
 
axes[1].plot(ttls, thr_ttl, marker="s", color=VERDE, linewidth=2, markersize=8)
axes[1].set_xlabel("TTL (segundos)")
axes[1].set_ylabel("Throughput (req/s)")
axes[1].set_title("Throughput segun TTL")
axes[1].set_xscale("log")
axes[1].grid(alpha=0.3)
for i, (t, v) in enumerate(zip(ttls, thr_ttl)):
    axes[1].annotate(f"{v}", (t, v), textcoords="offset points",
                     xytext=(5, 5), fontsize=9)
 
plt.suptitle("Impacto del TTL (200mb, LRU, Zipf)", fontweight="bold")
plt.tight_layout()
plt.savefig("graficos/05_impacto_ttl.png")
plt.close()
print("Grafico 5 guardado: graficos/05_impacto_ttl.png")
 
 
# ---------------------------------------------------------------------------
# Grafico 6: Resumen general - latencia p50 vs p95
# ---------------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(11, 5))
 
labels = [f"Exp {e['id']}\n{e['dist'][:3]}/{e['mem']}/{e['pol'][:3]}/TTL{e['ttl']}" for e in experimentos]
p50s = [e["p50"] for e in experimentos]
p95s = [e["p95"] for e in experimentos]
x = np.arange(len(labels))
w = 0.35
 
ax.bar(x - w/2, p50s, w, label="p50", color=AZUL, alpha=0.9)
ax.bar(x + w/2, p95s, w, label="p95", color=ROJO, alpha=0.6)
ax.set_xticks(x)
ax.set_xticklabels(labels, fontsize=8)
ax.set_ylabel("Latencia (ms)")
ax.set_title("Latencia p50 y p95 por experimento")
ax.legend()
ax.grid(axis="y", alpha=0.3)
ax.set_yscale("log")
 
plt.tight_layout()
plt.savefig("graficos/06_latencia_comparativa.png")
plt.close()
print("Grafico 6 guardado: graficos/06_latencia_comparativa.png")
 
print("\nTodos los graficos generados en la carpeta graficos/")
 

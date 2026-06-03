"""
generar_graficos_t2.py
Genera graficos comparativos para la Tarea 2 - Sistemas Distribuidos 2026-1
Datos actualizados con todos los experimentos (1000 consultas consistentes)
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import os

os.makedirs("graficos_t2", exist_ok=True)

C1 = "#2E86AB"  # azul
C2 = "#A23B72"  # morado
C3 = "#F18F01"  # naranja
C4 = "#C73E1D"  # rojo
C5 = "#3B1F2B"  # oscuro
C6 = "#44BBA4"  # verde
GRID = dict(color="grey", linestyle="--", linewidth=0.5, alpha=0.5)

# ==============================================================================
# 1. Throughput comparativo - sincrono vs kafka escalamiento
# ==============================================================================
labels = ["Síncrono\n(T1)", "Kafka\n1 consumer", "Kafka\n2 consumers", "Kafka\n4 consumers"]
throughputs = [39.6, 15.2, 16.2, 16.4]
colors = [C1, C2, C3, C4]

fig, ax = plt.subplots(figsize=(10, 5))
bars = ax.bar(labels, throughputs, color=colors, width=0.5, edgecolor="white")
for bar, val in zip(bars, throughputs):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.3,
            f"{val:.1f}", ha="center", va="bottom", fontsize=11, fontweight="bold")
ax.set_ylabel("Throughput (req/s)", fontsize=12)
ax.set_title("Throughput: Síncrono vs Kafka con Escalamiento", fontsize=14, fontweight="bold")
ax.set_ylim(0, 50)
ax.grid(axis="y", **GRID)
ax.spines[["top", "right"]].set_visible(False)
plt.tight_layout()
plt.savefig("graficos_t2/01_throughput_escalamiento.png", dpi=150)
plt.close()
print("Grafico 1 generado")

# ==============================================================================
# 2. Latencia p50 y p95 - sincrono vs kafka
# ==============================================================================
esc = ["Síncrono\n(T1)", "Kafka\n1 consumer", "Kafka\n2 consumers", "Kafka\n4 consumers"]
p50 = [72.50, 43.36, 72.0, 95.0]
p95 = [1222.0, 66.32, 165.0, 570.0]

x = np.arange(len(esc))
width = 0.35

fig, ax = plt.subplots(figsize=(11, 5))
b1 = ax.bar(x - width/2, p50, width, label="p50", color=C1, edgecolor="white")
b2 = ax.bar(x + width/2, p95, width, label="p95", color=C2, edgecolor="white")
for bar in b1:
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 5,
            f"{bar.get_height():.0f}", ha="center", va="bottom", fontsize=9)
for bar in b2:
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 5,
            f"{bar.get_height():.0f}", ha="center", va="bottom", fontsize=9)
ax.set_xticks(x)
ax.set_xticklabels(esc)
ax.set_ylabel("Latencia (ms)", fontsize=12)
ax.set_title("Latencia p50 y p95: Síncrono vs Kafka", fontsize=14, fontweight="bold")
ax.legend()
ax.grid(axis="y", **GRID)
ax.spines[["top", "right"]].set_visible(False)
plt.tight_layout()
plt.savefig("graficos_t2/02_latencia_sincrono_kafka.png", dpi=150)
plt.close()
print("Grafico 2 generado")

# ==============================================================================
# 3. Escalamiento horizontal: throughput 1 vs 2 vs 4 consumers
# ==============================================================================
n_consumers = [1, 2, 4]
thr_normal = [15.2, 16.2, 16.4]
thr_falla  = [9.7, 11.5, 15.4]
thr_spike  = [11.0, 11.3, 12.7]

x = np.arange(len(n_consumers))
width = 0.25

fig, ax = plt.subplots(figsize=(10, 5))
b1 = ax.bar(x - width, thr_normal, width, label="Sin fallos", color=C1, edgecolor="white")
b2 = ax.bar(x,         thr_falla,  width, label="FAIL_RATE=0.3", color=C3, edgecolor="white")
b3 = ax.bar(x + width, thr_spike,  width, label="Spike 1500 consultas", color=C6, edgecolor="white")

for bar in list(b1) + list(b2) + list(b3):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.2,
            f"{bar.get_height():.1f}", ha="center", va="bottom", fontsize=8)

ax.set_xticks(x)
ax.set_xticklabels(["1 Consumer", "2 Consumers", "4 Consumers"])
ax.set_ylabel("Throughput total (req/s)", fontsize=12)
ax.set_title("Escalamiento Horizontal: Throughput por Escenario", fontsize=14, fontweight="bold")
ax.legend()
ax.grid(axis="y", **GRID)
ax.spines[["top", "right"]].set_visible(False)
plt.tight_layout()
plt.savefig("graficos_t2/03_escalamiento_throughput.png", dpi=150)
plt.close()
print("Grafico 3 generado")

# ==============================================================================
# 4. Recuperacion ante fallos: sincrono vs kafka
# ==============================================================================
categorias = ["Consultas\nexitosas", "Errores/\nPerdidas", "Reintentos"]
sincrono = [954, 46, 0]
kafka    = [1000, 0, 43]

x = np.arange(len(categorias))
width = 0.35

fig, ax = plt.subplots(figsize=(9, 5))
b1 = ax.bar(x - width/2, sincrono, width, label="Síncrono (T1)", color=C1, edgecolor="white")
b2 = ax.bar(x + width/2, kafka,    width, label="Kafka 1 consumer", color=C2, edgecolor="white")
for bar in list(b1) + list(b2):
    if bar.get_height() > 0:
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 5,
                f"{int(bar.get_height())}", ha="center", va="bottom", fontsize=10, fontweight="bold")
ax.set_xticks(x)
ax.set_xticklabels(categorias, fontsize=11)
ax.set_ylabel("Cantidad de consultas", fontsize=12)
ax.set_title("Recuperación ante Fallos: Síncrono vs Kafka\n(FAIL_RATE=0.3, 1000 consultas)", fontsize=13, fontweight="bold")
ax.legend()
ax.grid(axis="y", **GRID)
ax.spines[["top", "right"]].set_visible(False)
plt.tight_layout()
plt.savefig("graficos_t2/04_recuperacion_fallos.png", dpi=150)
plt.close()
print("Grafico 4 generado")

# ==============================================================================
# 5. Reintentos y DLQ por escenario
# ==============================================================================
esc_retry = ["Kafka 1C\nFAIL=0.3", "Kafka 2C\nFAIL=0.3", "Kafka 4C\nFAIL=0.3",
             "Falla total\nFAIL=1.0"]
reintentos = [43, 56, 49, 300]
dlq        = [0, 0, 0, 100]

x = np.arange(len(esc_retry))
width = 0.35

fig, ax = plt.subplots(figsize=(10, 5))
b1 = ax.bar(x - width/2, reintentos, width, label="Reintentos", color=C3, edgecolor="white")
b2 = ax.bar(x + width/2, dlq,        width, label="DLQ", color=C4, edgecolor="white")
for bar in list(b1) + list(b2):
    if bar.get_height() > 0:
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 2,
                f"{int(bar.get_height())}", ha="center", va="bottom", fontsize=10, fontweight="bold")
ax.set_xticks(x)
ax.set_xticklabels(esc_retry, fontsize=9)
ax.set_ylabel("Cantidad de mensajes", fontsize=12)
ax.set_title("Reintentos y DLQ por Escenario", fontsize=14, fontweight="bold")
ax.legend()
ax.grid(axis="y", **GRID)
ax.spines[["top", "right"]].set_visible(False)
plt.tight_layout()
plt.savefig("graficos_t2/05_reintentos_dlq.png", dpi=150)
plt.close()
print("Grafico 5 generado")

# ==============================================================================
# 6. Backlog durante spike (evolucion temporal)
# ==============================================================================
tiempo = [0, 5, 10, 20, 30, 40, 50, 60, 80, 100, 120, 136]
backlog_queries = [0, 1501, 1501, 1501, 1501, 1501, 1501, 1501, 1501, 1501, 1501, 0]
backlog_retry   = [0, 0, 5, 13, 20, 30, 42, 51, 54, 54, 54, 0]

fig, ax = plt.subplots(figsize=(11, 5))
ax.plot(tiempo, backlog_queries, color=C1, linewidth=2, marker="o", markersize=5, label="queries")
ax.plot(tiempo, backlog_retry,   color=C3, linewidth=2, marker="s", markersize=5, label="queries-retry")
ax.axvline(x=5, color="red", linestyle="--", linewidth=1.5, alpha=0.7, label="Spike publicado")
ax.axvline(x=136, color="green", linestyle="--", linewidth=1.5, alpha=0.7, label="Cola vaciada (136s)")
ax.fill_between(tiempo, backlog_queries, alpha=0.1, color=C1)
ax.set_xlabel("Tiempo (s)", fontsize=12)
ax.set_ylabel("Mensajes en cola", fontsize=12)
ax.set_title("Evolución del Backlog durante Spike\n(1 Consumer, 1500 consultas)", fontsize=13, fontweight="bold")
ax.legend()
ax.grid(**GRID)
ax.spines[["top", "right"]].set_visible(False)
plt.tight_layout()
plt.savefig("graficos_t2/06_backlog_spike.png", dpi=150)
plt.close()
print("Grafico 6 generado")

# ==============================================================================
# 7. Latencia p95 bajo fallos: 1 vs 2 vs 4 consumers
# ==============================================================================
consumers_labels = ["1 Consumer", "2 Consumers", "4 Consumers"]
p95_falla = [56.55, 149.0, 362.0]
p95_spike = [109.29, 222.0, 770.0]
p95_normal = [66.32, 165.0, 570.0]

x = np.arange(len(consumers_labels))
width = 0.25

fig, ax = plt.subplots(figsize=(10, 5))
b1 = ax.bar(x - width, p95_normal, width, label="Sin fallos", color=C1, edgecolor="white")
b2 = ax.bar(x,         p95_falla,  width, label="FAIL_RATE=0.3", color=C3, edgecolor="white")
b3 = ax.bar(x + width, p95_spike,  width, label="Spike", color=C6, edgecolor="white")

ax.set_xticks(x)
ax.set_xticklabels(consumers_labels)
ax.set_ylabel("Latencia p95 (ms)", fontsize=12)
ax.set_title("Latencia p95 por Escenario y Número de Consumers", fontsize=13, fontweight="bold")
ax.legend()
ax.grid(axis="y", **GRID)
ax.spines[["top", "right"]].set_visible(False)
plt.tight_layout()
plt.savefig("graficos_t2/07_latencia_p95_escenarios.png", dpi=150)
plt.close()
print("Grafico 7 generado")

# ==============================================================================
# 8. Recovery rate: sincrono vs kafka por escenario de fallo
# ==============================================================================
esc_rec = ["Síncrono\nFAIL=0.3", "Kafka 1C\nFAIL=0.3", "Kafka 2C\nFAIL=0.3",
           "Kafka 4C\nFAIL=0.3", "Kafka\nFAIL=1.0"]
recovery = [95.4, 100.0, 100.0, 100.0, 0.0]
colors_rec = [C1, C2, C3, C4, C5]

fig, ax = plt.subplots(figsize=(10, 5))
bars = ax.bar(esc_rec, recovery, color=colors_rec, width=0.5, edgecolor="white")
for bar, val in zip(bars, recovery):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5,
            f"{val:.1f}%", ha="center", va="bottom", fontsize=11, fontweight="bold")
ax.set_ylabel("Recovery Rate (%)", fontsize=12)
ax.set_title("Recovery Rate por Escenario de Fallo", fontsize=14, fontweight="bold")
ax.set_ylim(0, 115)
ax.axhline(y=100, color="green", linestyle="--", linewidth=1.5, alpha=0.7, label="100% recovery")
ax.legend()
ax.grid(axis="y", **GRID)
ax.spines[["top", "right"]].set_visible(False)
plt.tight_layout()
plt.savefig("graficos_t2/08_recovery_rate.png", dpi=150)
plt.close()
print("Grafico 8 generado")

print("\nTodos los graficos generados en graficos_t2/")

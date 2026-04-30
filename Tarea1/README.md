# Tarea 1 - Sistemas Distribuidos 2026-1
Plataforma de analisis de preguntas y respuestas en Internet

Profesor: Nicolas Hidalgo
Ayudantes: Isidora Gonzalez, Natalia Ortega, Joaquin Villegas, Vicente Diaz y Benjamin Aceituno
Integrantes: Isidora Bravo Ortiz - Mateo Solari López 


## Descripcion

Sistema distribuido de caché para consultas geoespaciales sobre el dataset Google Open Buildings
de la Region Metropolitana de Santiago de Chile. El sistema optimiza el acceso a informacion
sobre edificaciones mediante un cache Redis, reduciendo la latencia y mejorando el rendimiento
bajo distintos patrones de carga.


## Arquitectura

El sistema esta compuesto por 4 servicios independientes que se comunican de forma secuencial:

    Generador de Trafico --> Sistema de Cache (Redis) --> Generador de Respuestas
                                       |
                           Almacenamiento de Metricas

1. Generador de Trafico: simula consultas de empresas de logistica siguiendo distribuciones
   Zipf y uniforme.

2. Sistema de Cache: intercepta consultas usando Redis con TTL y politicas de reemplazo
   configurables (LRU, LFU, Random).

3. Generador de Respuestas: procesa consultas Q1-Q5 directamente en memoria sobre el
   dataset precargado.

4. Almacenamiento de Metricas: registra hits, misses, latencias, throughput y eviction
   rate en SQLite.


## Requisitos

- Docker >= 20.x
- Docker Compose >= 1.29
- 4 GB de RAM disponibles
- 2 GB de espacio en disco


## Dataset

El sistema utiliza el dataset Google Open Buildings filtrado para la Region Metropolitana.

Pasos para obtenerlo:
1. Ir a https://sites.research.google/gr/open-buildings/
2. Descargar el archivo .csv.gz correspondiente a Chile
3. Descomprimir: gunzip archivo.csv.gz
4. Filtrar solo la RM con el siguiente comando:

    python3 -c "
    import csv
    input_file = 'archivo.csv'
    output_file = 'data/open_buildings_rm.csv'
    count = 0
    with open(input_file) as fin, open(output_file, 'w', newline='') as fout:
        reader = csv.DictReader(fin)
        writer = csv.DictWriter(fout, fieldnames=reader.fieldnames)
        writer.writeheader()
        for row in reader:
            lat = float(row['latitude'])
            lon = float(row['longitude'])
            if -34.0 <= lat <= -33.0 and -71.0 <= lon <= -70.0:
                writer.writerow(row)
                count += 1
    print(f'Edificios encontrados: {count}')
    "

Sin dataset real el sistema genera datos sinteticos automaticamente.


## Despliegue

Clonar el repositorio:

```bash
git clone https://github.com/AndreiwSnow/Sistemas-Distribuidos.git
cd Sistemas-Distribuidos/Tarea1


## Configuracion de experimentos

Todas las variables se controlan desde docker-compose.yml.

Distribucion de trafico (seccion traffic_generator > environment):

    DISTRIBUTION=zipf       opciones: zipf | uniform
    ZIPF_S=1.2              parametro s de Zipf
    TOTAL_REQUESTS=1000     numero de consultas
    CONCURRENCY=10          consultas paralelas

Tamano y politica del cache (seccion redis > command):

    --maxmemory 200mb                  opciones: 50mb | 200mb | 500mb
    --maxmemory-policy allkeys-lru     opciones: allkeys-lru | allkeys-lfu | allkeys-random

TTL del cache (seccion cache_service > environment):

    TTL=60     segundos, opciones: 30 | 60 | 300

Para correr un experimento nuevo:

    docker-compose down -v && docker-compose up


## Endpoints disponibles

Generador de respuestas (puerto 8001):
    GET  /health
    POST /query

Cache (puerto 8002):
    GET  /health
    POST /query

Metricas (puerto 8003):
    GET    /health
    GET    /metrics
    GET    /metrics/summary
    GET    /metrics/evictions
    DELETE /metrics/reset


## Ver metricas

Resumen completo con hit rate, latencias, throughput, eviction rate y cache efficiency:

    curl http://localhost:8003/metrics/summary

Historial de evictions:

    curl http://localhost:8003/metrics/evictions

Limpiar metricas entre experimentos:

    curl -X DELETE http://localhost:8003/metrics/reset


## Tipos de consultas

Q1: conteo de edificios en una zona.          Cache key: count:{zona_id}:conf={confidence_min}
Q2: area promedio y total de edificaciones.   Cache key: area:{zona_id}:conf={confidence_min}
Q3: densidad de edificaciones por km2.        Cache key: density:{zona_id}:conf={confidence_min}
Q4: comparacion de densidad entre dos zonas.  Cache key: compare:density:{zona_a}:{zona_b}:conf={confidence_min}
Q5: distribucion de confianza en una zona.    Cache key: confidence_dist:{zona_id}:bins={bins}


## Zonas predefinidas

Z1 Providencia:     lat -33.445 a -33.420 | lon -70.640 a -70.600
Z2 Las Condes:      lat -33.420 a -33.390 | lon -70.600 a -70.550
Z3 Maipu:           lat -33.530 a -33.490 | lon -70.790 a -70.740
Z4 Santiago Centro: lat -33.460 a -33.430 | lon -70.670 a -70.630
Z5 Pudahuel:        lat -33.470 a -33.430 | lon -70.810 a -70.760


## Estructura del repositorio

    tarea1-sd/
    ├── docker-compose.yml
    ├── README.md
    ├── .gitignore
    ├── generar_graficos.py
    ├── data/                        (dataset CSV, no se sube a git)
    ├── response_generator/
    │   ├── Dockerfile
    │   ├── responder.py
    │   └── data_loader.py
    ├── cache_service/
    │   ├── Dockerfile
    │   └── cache.py
    ├── traffic_generator/
    │   ├── Dockerfile
    │   ├── generator.py
    │   └── queries.py
    └── metrics/
        ├── Dockerfile
        └── metrics.py


## Detener el sistema

    docker-compose down
    docker-compose down -v     (elimina tambien los volumenes de metricas)


## Generar graficos

    pip3 install matplotlib numpy --break-system-packages
    python3 generar_graficos.py
    (los graficos se guardan en la carpeta graficos/)

# Tarea 1 - Sistemas Distribuidos 2026-1

Plataforma de análisis de preguntas y respuestas en Internet

Profesor: Nicolás Hidalgo  
Ayudantes: Isidora González, Natalia Ortega, Joaquín Villegas, Vicente Díaz y Benjamín Aceituno  
Integrantes: Isidora Bravo Ortiz - Mateo Solari López 


## Descripción

Sistema distribuido de caché para consultas geoespaciales sobre el dataset Google Open Buildings
de la Región Metropolitana de Santiago de Chile. El sistema optimiza el acceso a información
sobre edificaciones mediante un caché Redis, reduciendo la latencia y mejorando el rendimiento
bajo distintos patrones de carga.


## Arquitectura

El sistema está compuesto por 4 servicios independientes que se comunican de forma secuencial:

```txt
Generador de Tráfico --> Sistema de Caché (Redis) --> Generador de Respuestas
                                   |
                       Almacenamiento de Métricas
```

1. Generador de Tráfico: simula consultas de empresas de logística siguiendo distribuciones
   Zipf y uniforme.

2. Sistema de Caché: intercepta consultas usando Redis con TTL y políticas de reemplazo
   configurables (LRU, LFU, Random).

3. Generador de Respuestas: procesa consultas Q1-Q5 directamente en memoria sobre el
   dataset precargado.

4. Almacenamiento de Métricas: registra hits, misses, latencias, throughput y eviction
   rate en SQLite.


## Requisitos

- Docker >= 20.x
- Docker Compose >= 1.29
- 4 GB de RAM disponibles
- 2 GB de espacio en disco


## Dataset

El sistema fue diseñado para trabajar con el dataset **Google Open Buildings** filtrado para la Región Metropolitana de Santiago de Chile.

Por temas de tamaño, la carpeta `data/` y el archivo `open_buildings_rm.csv` **no fueron incluidos en el repositorio de GitHub**. Esto se debe a que el dataset original es demasiado pesado para ser subido directamente al repositorio.

El archivo esperado por el sistema es:

```bash
data/open_buildings_rm.csv
```

Si se desea ejecutar el sistema con el dataset real, se debe crear manualmente la carpeta `data/` dentro de `Tarea1` y colocar ahí el archivo CSV filtrado:

```bash
mkdir data
cp /ruta/al/open_buildings_rm.csv data/open_buildings_rm.csv
```

Pasos para obtener el dataset:

1. Ir a https://sites.research.google/gr/open-buildings/
2. Descargar el archivo `.csv.gz` correspondiente a Chile.
3. Descomprimir el archivo:

```bash
gunzip archivo.csv.gz
```

4. Filtrar solo los datos correspondientes a la Región Metropolitana con el siguiente comando:

```bash
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
```

En caso de no contar con el dataset real, el sistema puede generar datos sintéticos automáticamente para permitir pruebas básicas de funcionamiento.


## Despliegue

Clonar el repositorio:

```bash
git clone https://github.com/AndreiwSnow/Sistemas-Distribuidos.git
cd Sistemas-Distribuidos/Tarea1
```

Crear la carpeta del dataset, si se desea usar el archivo real:

```bash
mkdir data
cp /ruta/al/open_buildings_rm.csv data/open_buildings_rm.csv
```

Si no se cuenta con el dataset real, se puede omitir este paso y el sistema utilizará datos sintéticos.

Levantar todos los servicios:

```bash
docker-compose up --build
```


## Configuración de experimentos

Todas las variables se controlan desde `docker-compose.yml`.

Distribución de tráfico, en la sección `traffic_generator > environment`:

```bash
DISTRIBUTION=zipf       opciones: zipf | uniform
ZIPF_S=1.2              parámetro s de Zipf
TOTAL_REQUESTS=1000     número de consultas
CONCURRENCY=10          consultas paralelas
```

Tamaño y política del caché, en la sección `redis > command`:

```bash
--maxmemory 200mb                  opciones: 50mb | 200mb | 500mb
--maxmemory-policy allkeys-lru     opciones: allkeys-lru | allkeys-lfu | allkeys-random
```

TTL del caché, en la sección `cache_service > environment`:

```bash
TTL=60     segundos, opciones: 30 | 60 | 300
```

Para correr un experimento nuevo:

```bash
docker-compose down -v && docker-compose up
```


## Endpoints disponibles

Generador de respuestas, puerto 8001:

```bash
GET  /health
POST /query
```

Caché, puerto 8002:

```bash
GET  /health
POST /query
```

Métricas, puerto 8003:

```bash
GET    /health
GET    /metrics
GET    /metrics/summary
GET    /metrics/evictions
DELETE /metrics/reset
```


## Ver métricas

Resumen completo con hit rate, latencias, throughput, eviction rate y cache efficiency:

```bash
curl http://localhost:8003/metrics/summary
```

Historial de evictions:

```bash
curl http://localhost:8003/metrics/evictions
```

Limpiar métricas entre experimentos:

```bash
curl -X DELETE http://localhost:8003/metrics/reset
```


## Tipos de consultas

```txt
Q1: conteo de edificios en una zona.
Cache key: count:{zona_id}:conf={confidence_min}

Q2: área promedio y total de edificaciones.
Cache key: area:{zona_id}:conf={confidence_min}

Q3: densidad de edificaciones por km2.
Cache key: density:{zona_id}:conf={confidence_min}

Q4: comparación de densidad entre dos zonas.
Cache key: compare:density:{zona_a}:{zona_b}:conf={confidence_min}

Q5: distribución de confianza en una zona.
Cache key: confidence_dist:{zona_id}:bins={bins}
```


## Zonas predefinidas

```txt
Z1 Providencia:     lat -33.445 a -33.420 | lon -70.640 a -70.600
Z2 Las Condes:      lat -33.420 a -33.390 | lon -70.600 a -70.550
Z3 Maipú:           lat -33.530 a -33.490 | lon -70.790 a -70.740
Z4 Santiago Centro: lat -33.460 a -33.430 | lon -70.670 a -70.630
Z5 Pudahuel:        lat -33.470 a -33.430 | lon -70.810 a -70.760
```


## Estructura del repositorio

```txt
Tarea1/
├── docker-compose.yml
├── README.md
├── .gitignore
├── generar_graficos.py
├── data/                        (carpeta excluida por tamaño; aquí va open_buildings_rm.csv)
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
```

La carpeta `data/` no está incluida en GitHub. Debe crearse manualmente solo si se desea ejecutar el sistema con el dataset real.


## Detener el sistema

Detener los servicios:

```bash
docker-compose down
```

Detener los servicios y eliminar también los volúmenes de métricas:

```bash
docker-compose down -v
```


## Generar gráficos

Instalar dependencias necesarias:

```bash
pip3 install matplotlib numpy --break-system-packages
```

Ejecutar el script:

```bash
python3 generar_graficos.py
```

Los gráficos se guardan automáticamente en la carpeta `graficos/`.

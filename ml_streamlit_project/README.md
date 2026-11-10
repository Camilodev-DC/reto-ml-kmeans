# Segmentación con K-Means

**Autores:** ✏️ Nombre 1 · Nombre 2

## Objetivo
✏️ Describe en 2 o 3 líneas qué perfiles se quieren descubrir y para qué sirven.

## Dataset
- **Descripción y fuente:** ✏️
- **Unidad de observación (qué es una fila):** ✏️
- **Tamaño:** 178 filas × 13 columnas (178 filas tras la limpieza).
- **Ubicación:** `data/datos.csv`. ✏️ Si el dataset no se puede publicar, explica aquí cómo obtenerlo y dónde ubicarlo.

## Ruta elegida
**Ruta B: aprendizaje no supervisado.** Segmentación con K-Means. No se usa variable objetivo.

## Variables utilizadas
- `alcohol` (numérica)
- `malic_acid` (numérica, con log)
- `ash` (numérica)
- `alcalinity_of_ash` (numérica)
- `magnesium` (numérica)
- `total_phenols` (numérica)
- `flavanoids` (numérica)
- `nonflavanoid_phenols` (numérica)
- `proanthocyanins` (numérica)
- `color_intensity` (numérica)
- `hue` (numérica)
- `od280/od315_of_diluted_wines` (numérica)
- `proline` (numérica)


Variables excluidas:

Ninguna.

## Preparación de datos
Limpieza por filas (solo entrenamiento):
- Eliminar filas duplicadas: sí (filas eliminadas: 0).
- Eliminar filas con más del 50% de faltantes (filas eliminadas: 0).

Dentro del pipeline (se aplica igual en entrenamiento y en la app):
1. Conversión de texto a número (`"$ 1.234.567"`, `"45,9"`, `"15%"`).
2. Imputación de faltantes numéricos: `median`.
3. Transformación log en variables sesgadas: ['malic_acid'].
4. Tratamiento de atípicos (recorte): `iqr`.
5. Escalado: `standard`.
6. Categóricas: limpieza de texto, imputación `most_frequent` y one-hot encoding.

## Modelo y justificación
K-Means con **k = 3** (`random_state = 42`, `n_init = 10`). K-Means permite asignar casos nuevos con `predict()`, que es lo que necesita la app.

✏️ Justifica la elección de k con la tabla siguiente (codo, silhouette y tamaño mínimo de cluster) y con la interpretabilidad de los perfiles.

| k | inercia | silhouette | davies_bouldin | calinski_harabasz | cluster_min_% |
|---|---|---|---|---|---|
| 2 | 1,655.062 | 0.268 | 1.449 | 70.072 | 36.517 |
| 3 | 1,265.348 | 0.287 | 1.382 | 72.515 | 28.652 |
| 4 | 1,168.972 | 0.253 | 1.785 | 56.812 | 16.292 |
| 5 | 1,092.332 | 0.230 | 1.727 | 48.371 | 12.360 |
| 6 | 1,039.469 | 0.140 | 1.990 | 42.179 | 15.169 |
| 7 | 990.014 | 0.126 | 1.943 | 38.114 | 8.989 |
| 8 | 930.564 | 0.146 | 1.789 | 36.105 | 6.180 |

## Evaluación
| Métrica | Valor |
|---|---|
| Silhouette | 0.287 |
| Davies-Bouldin | 1.382 |
| Calinski-Harabasz | 72.5 |
| Inercia | 1265.3 |
| Estabilidad (ARI medio en submuestras del 80 %) | 0.99 |

## Interpretación de la salida
La app devuelve el **cluster asignado** y la descripción de su perfil:

| Cluster | Nombre | Descripción |
|---|---|---|
| 0 | ↓ alcohol · ↓ color_intensity | 65 casos (36%): Por debajo del promedio en alcohol (-0.9 DE); por debajo del promedio en color_intensity (-0.9 DE); por debajo del promedio en proline (-0.8 DE). |
| 1 | ↓ od280/od315_of_diluted_wines · ↓ flavanoids | 51 casos (29%): Por debajo del promedio en od280/od315_of_diluted_wines (-1.3 DE); por debajo del promedio en flavanoids (-1.2 DE); por debajo del promedio en hue (-1.2 DE). |
| 2 | ↑ proline · ↑ flavanoids | 62 casos (35%): Por encima del promedio en proline (+1.1 DE); por encima del promedio en flavanoids (+1.0 DE); por encima del promedio en total_phenols (+0.9 DE). |

Perfiles promedio (unidades originales):

| cluster | n_casos | porcentaje | alcohol | malic_acid | ash | alcalinity_of_ash | magnesium | total_phenols | flavanoids | nonflavanoid_phenols | proanthocyanins | color_intensity | hue | od280/od315_of_diluted_wines | proline |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 65 | 36.50 | 12.25 | 1.90 | 2.23 | 20.06 | 92.74 | 2.25 | 2.05 | 0.36 | 1.62 | 2.97 | 1.06 | 2.80 | 510.17 |
| 1 | 51 | 28.70 | 13.13 | 3.31 | 2.42 | 21.24 | 98.67 | 1.68 | 0.82 | 0.45 | 1.15 | 7.24 | 0.69 | 1.70 | 619.06 |
| 2 | 62 | 34.80 | 13.68 | 2.00 | 2.47 | 17.46 | 107.97 | 2.85 | 3.00 | 0.29 | 1.92 | 5.45 | 1.06 | 3.16 | 1,100.23 |

## Cómo ejecutar
### Entrenar
```bash
pip install -r requirements.txt
python train.py
```
### Streamlit (local)
```bash
streamlit run app.py
```
### Docker
```bash
docker build -t ml-streamlit-app .
docker run -d --name ml-streamlit --restart unless-stopped -p 8501:8501 ml-streamlit-app
```
Abrir `http://localhost:8501` (o `http://IP_EXTERNA_DE_LA_VM:8501` en GCP, con el puerto 8501 abierto en el firewall).

### Google Cloud (VM Ubuntu 24.04)
```bash
sudo apt update && sudo apt install -y docker.io git
sudo systemctl enable --now docker
git clone <URL_DEL_REPOSITORIO>
cd <NOMBRE_DEL_REPOSITORIO>
sudo docker build -t ml-streamlit-app .
sudo docker run -d --name ml-streamlit --restart unless-stopped -p 8501:8501 ml-streamlit-app
```

## Ejemplo de entrada y salida
Entrada (caso típico: medianas y categorías más frecuentes):
```json
{
  "alcohol": 13.05,
  "malic_acid": 1.865,
  "ash": 2.36,
  "alcalinity_of_ash": 19.5,
  "magnesium": 98,
  "total_phenols": 2.355,
  "flavanoids": 2.135,
  "nonflavanoid_phenols": 0.34,
  "proanthocyanins": 1.555,
  "color_intensity": 4.69,
  "hue": 0.965,
  "od280/od315_of_diluted_wines": 2.78,
  "proline": 674
}
```
Salida esperada: **Cluster 0: ↓ alcohol · ↓ color_intensity**

## Estructura
```
app.py            interfaz Streamlit
train.py          entrenamiento reproducible
cluster_utils.py  limpieza, pipeline y perfiles
config.json       decisiones de variables, limpieza y k
model.joblib      pipeline entrenado
requirements.txt  dependencias con versión fija
Dockerfile, .dockerignore
data/datos.csv
```

Versiones usadas: python 3.13.17, scikit-learn 1.9.1, pandas 3.1.0, numpy 2.5.4.

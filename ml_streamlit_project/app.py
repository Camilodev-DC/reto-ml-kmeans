"""
app.py - interfaz Streamlit de la Ruta B (clustering con K-Means).

Carga model.joblib (NO vuelve a entrenar), recibe un caso nuevo o un archivo
con varios casos y devuelve el cluster asignado con su descripcion.
"""
import sys
from pathlib import Path

import joblib
import pandas as pd
import streamlit as st

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

import cluster_utils as cu  # noqa: E402  (necesario para cargar las clases del pipeline)

st.set_page_config(page_title="Segmentación K-Means", page_icon="🧩", layout="wide")


@st.cache_resource
def load_artifact():
    return joblib.load(BASE_DIR / "model.joblib")


artifact = load_artifact()

model = artifact["model"]
features = artifact["features"]
numeric_features = artifact.get("numeric_features", [])
categorical_features = artifact.get("categorical_features", [])
task = artifact["task"]
names = artifact.get("cluster_names", {})
descriptions = artifact.get("cluster_descriptions", {})
stats = artifact.get("numeric_stats", {})
options = artifact.get("category_options", {})
defaults = artifact.get("category_defaults", {})
metrics = artifact.get("metrics", {})
profiles = pd.DataFrame(artifact.get("profiles", []))
if not profiles.empty:
    profiles = profiles.set_index("cluster")


def cluster_label(c: int) -> str:
    name = names.get(int(c), "")
    return f"Cluster {c} · {name}" if name else f"Cluster {c}"


def fmt(x) -> str:
    return f"{x:,.4g}"


# ---------------------------------------------------------------------------
st.title(artifact.get("title", "Segmentación con K-Means"))
st.write(
    "Ingrese las características de un caso nuevo y el modelo lo asignará al grupo "
    "(cluster) más parecido. El modelo no se reentrena: aplica el mismo pipeline "
    "de limpieza y escalado que se usó en el entrenamiento."
)

with st.sidebar:
    st.header("Modelo")
    st.metric("Número de clusters (k)", artifact.get("n_clusters", "-"))
    if "silhouette" in metrics:
        st.metric("Silhouette", f"{metrics['silhouette']:.3f}",
                  help="De -1 a 1. Más alto = clusters más separados.")
    if "estabilidad_ari_media" in metrics:
        st.metric("Estabilidad (ARI)", f"{metrics['estabilidad_ari_media']:.2f}",
                  help="Qué tanto se repiten los clusters al reentrenar con submuestras. 1 = idénticos.")
    st.metric("Filas de entrenamiento", artifact.get("n_rows_train", "-"))
    st.caption("Variables: " + ", ".join(features))

tab_case, tab_batch, tab_profiles = st.tabs(["Un caso", "Varios casos (archivo)", "Perfiles de los clusters"])

# ---------------------------------------------------------------------------
with tab_case:
    with st.form("nuevo_caso"):
        values = {}
        columns = st.columns(2)
        for i, feature in enumerate(numeric_features):
            s = stats.get(feature)
            col = columns[i % 2]
            if s is None:
                values[feature] = col.number_input(feature, value=0.0)
                continue
            help_text = f"En entrenamiento: mín {fmt(s['min'])} · mediana {fmt(s['median'])} · máx {fmt(s['max'])}"
            if s.get("is_integer"):
                values[feature] = col.number_input(feature, value=int(round(s["median"])), step=1, help=help_text)
            else:
                values[feature] = col.number_input(feature, value=float(s["median"]), help=help_text)
        for j, feature in enumerate(categorical_features):
            opts = options.get(feature, [])
            col = columns[(len(numeric_features) + j) % 2]
            if opts:
                default = defaults.get(feature)
                index = opts.index(default) if default in opts else 0
                values[feature] = col.selectbox(feature, opts, index=index)
            else:
                values[feature] = col.text_input(feature)
        submitted = st.form_submit_button("Ejecutar modelo", type="primary")

    if submitted:
        X_new = pd.DataFrame([values], columns=features)
        result = int(model.predict(X_new)[0])

        if task == "clustering":
            st.success(f"Cluster asignado: **{cluster_label(result)}**")
            st.info(descriptions.get(result, "Sin descripción"))

        outside = cu.out_of_range(artifact, values)
        if outside:
            st.warning(
                "Valores fuera del rango visto en entrenamiento: " + ", ".join(outside)
                + ". El pipeline los recorta, pero la asignación puede ser menos confiable."
            )

        left, right = st.columns(2)
        distances = model.transform(X_new)[0]
        dist_df = pd.DataFrame(
            {"Distancia al centro": distances},
            index=[cluster_label(c) for c in range(len(distances))],
        )
        left.write("**Distancia al centro de cada cluster** (menor = más parecido)")
        left.bar_chart(dist_df, horizontal=True)

        if numeric_features and not profiles.empty:
            comparison = pd.DataFrame({
                "Este caso": [values[f] for f in numeric_features],
                f"Promedio cluster {result}": [profiles.loc[result, f] for f in numeric_features],
                "Promedio general": [artifact["global_means"][f] for f in numeric_features],
            }, index=numeric_features)
            right.write("**Comparación con el perfil del cluster**")
            right.dataframe(comparison.round(2))

# ---------------------------------------------------------------------------
with tab_batch:
    st.write(
        "Suba un CSV o Excel con estas columnas: **" + ", ".join(features) + "**. "
        "Las columnas adicionales se conservan en el resultado."
    )
    uploaded = st.file_uploader("Archivo", type=["csv", "xlsx", "xls"])
    if uploaded is not None:
        try:
            df_in = cu.load_table(uploaded, name=uploaded.name)
            result_df = cu.assign_clusters(artifact, df_in)
        except Exception as exc:  # mensaje claro en lugar de un traceback
            st.error(f"No se pudo procesar el archivo: {exc}")
        else:
            counts = result_df["cluster"].map(cluster_label).value_counts().sort_index()
            st.write(f"Se asignaron **{len(result_df)}** casos.")
            st.bar_chart(counts.rename("Casos"), horizontal=True)
            st.dataframe(result_df.head(500))
            st.download_button(
                "Descargar resultados (CSV)",
                result_df.to_csv(index=False).encode("utf-8"),
                file_name="resultados_clusters.csv",
                mime="text/csv",
            )

# ---------------------------------------------------------------------------
with tab_profiles:
    st.write("Promedios de cada cluster en las unidades originales de los datos.")
    if not profiles.empty:
        st.dataframe(profiles)
    for c in sorted(descriptions):
        st.markdown(f"**{cluster_label(c)}** — {descriptions[c]}")

"""
app.py - interfaz Streamlit de la Ruta B (clustering con K-Means).

Carga model.joblib (NO vuelve a entrenar), recibe un caso nuevo o un archivo
con varios casos y devuelve el cluster asignado con su descripcion.

Diseño: portada.py (pantalla de inicio) y estilos.py (CSS de la app).
"""
import html
import sys
from pathlib import Path

import joblib
import pandas as pd
import streamlit as st

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

import cluster_utils as cu  # noqa: E402  (necesario para cargar las clases del pipeline)

st.set_page_config(page_title="Segmentación K-Means", page_icon="🧩", layout="wide")


from portada import mostrar_portada  # noqa: E402
mostrar_portada()

import estilos  # noqa: E402
estilos.aplicar()

# Textos del encabezado
TITULO_APP = "Perfiles de vinos"
SUBTITULO_APP = "Ingresa la composición química de un vino y el modelo lo ubica en el grupo más parecido."


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


def rasgos(c: int, top: int = 3) -> str:
    """Las variables donde el cluster mas se aleja del promedio (en desviaciones estandar)."""
    if profiles.empty:
        return ""
    z = []
    for f in numeric_features:
        s = stats.get(f)
        if not s or not s.get("std"):
            continue
        z.append((f, (profiles.loc[c, f] - s["mean"]) / s["std"]))
    z.sort(key=lambda t: abs(t[1]), reverse=True)
    return " · ".join(("↑ " if v > 0 else "↓ ") + f for f, v in z[:top])


def tarjetas_clusters() -> None:
    """Una tarjeta por cluster: color, porcentaje, nombre y rasgos principales."""
    if profiles.empty:
        return
    cards = []
    for c in profiles.index:
        n = int(profiles.loc[c, "n_casos"])
        pct = float(profiles.loc[c, "porcentaje"])
        cards.append(f"""
        <div class="vidrio cl" style="border-top-color:{estilos.color_cluster(c)}">
          <span class="pct">{pct:.0f}% · {n} CASOS</span>
          <h4>{html.escape(names.get(int(c), f"Cluster {c}"))}</h4>
          <p>Cluster {c} · {html.escape(rasgos(c))}</p>
        </div>""")
    st.html(f'<div class="clusters">{"".join(cards)}</div>')


# ---------------------------------------------------------------------------
# Encabezado y metricas (antes estaban en el sidebar)
# ---------------------------------------------------------------------------
st.html(f"""
<p class="enc-k">SEGMENTACIÓN DE K-MEANS</p>
<p class="enc-h">{html.escape(TITULO_APP)}</p>
<p class="enc-s">{html.escape(SUBTITULO_APP)}</p>
<div class="kpis">
  <div class="vidrio kpi"><p>CLUSTERS</p><b>{artifact.get("n_clusters", "-")}</b></div>
  <div class="vidrio kpi" title="De -1 a 1. Más alto = clusters más separados.">
    <p>SILHOUETTE</p><b>{metrics.get("silhouette", float("nan")):.3f}</b></div>
  <div class="vidrio kpi" title="Qué tanto se repiten los clusters al reentrenar con submuestras. 1 = idénticos.">
    <p>ESTABILIDAD (ARI)</p><b>{metrics.get("estabilidad_ari_media", float("nan")):.2f}</b></div>
  <div class="vidrio kpi"><p>FILAS DE ENTRENAMIENTO</p><b>{artifact.get("n_rows_train", "-")}</b></div>
</div>
""")

tab_case, tab_batch, tab_profiles = st.tabs(
    ["Clasificar un vino", "Varios vinos (archivo)", "Perfiles de los clusters"]
)

# ---------------------------------------------------------------------------
with tab_case:
    col_form, col_res = st.columns([1.15, 1], gap="medium")

    with col_form:
        with st.form("nuevo_caso"):
            st.markdown('<p class="etiqueta">COMPOSICIÓN</p>', unsafe_allow_html=True)
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
            submitted = st.form_submit_button("Clasificar")

    with col_res:
        if submitted:
            X_new = pd.DataFrame([values], columns=features)
            result = int(model.predict(X_new)[0])
            distances = model.transform(X_new)[0]
            d_max = max(float(distances.max()), 1e-9)

            barras = "".join(f"""
            <div class="barra-fila">
              <span>Cluster {c}</span>
              <div class="barra"><i style="width:{float(d) / d_max * 100:.0f}%;background:{estilos.color_cluster(c)}"></i></div>
              <span>{float(d):.2f}</span>
            </div>""" for c, d in enumerate(distances))

            st.html(f"""
            <div class="vidrio resultado">
              <p class="etiqueta">RESULTADO</p>
              <div class="res-fila">
                <span class="punto" style="background:{estilos.color_cluster(result)}"></span>
                <p class="res-nombre">{html.escape(cluster_label(result))}</p>
              </div>
              <p class="res-desc">{html.escape(descriptions.get(result, "Sin descripción"))}</p>
              <p class="etiqueta">DISTANCIA AL CENTRO DE CADA GRUPO (menor = más parecido)</p>
              {barras}
            </div>
            """)

            outside = cu.out_of_range(artifact, values)
            if outside:
                st.warning(
                    "Valores fuera del rango visto en entrenamiento: " + ", ".join(outside)
                    + ". El pipeline los recorta, pero la asignación puede ser menos confiable."
                )
        else:
            st.html("""
            <div class="vidrio vacio">
              <p class="grande">¿A qué grupo pertenece?</p>
              <p>Ajusta la composición del vino y presiona <b>Clasificar</b>.</p>
            </div>
            """)

    if submitted and numeric_features and not profiles.empty:
        with st.expander("Comparación con el perfil del cluster"):
            comparison = pd.DataFrame({
                "Este caso": [values[f] for f in numeric_features],
                f"Promedio cluster {result}": [profiles.loc[result, f] for f in numeric_features],
                "Promedio general": [artifact["global_means"][f] for f in numeric_features],
            }, index=numeric_features)
            st.dataframe(comparison.round(2))

    st.markdown('<p class="etiqueta" style="margin-top:1.2em">LOS GRUPOS</p>', unsafe_allow_html=True)
    tarjetas_clusters()

# ---------------------------------------------------------------------------
with tab_batch:
    st.write(
        "Sube un CSV o Excel con estas columnas: **" + ", ".join(features) + "**. "
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
    tarjetas_clusters()
    st.write("Promedios de cada cluster en las unidades originales de los datos.")
    if not profiles.empty:
        st.dataframe(profiles)
    for c in sorted(descriptions):
        st.markdown(f"**{cluster_label(c)}** — {descriptions[c]}")
    st.caption("Variables: " + ", ".join(features))

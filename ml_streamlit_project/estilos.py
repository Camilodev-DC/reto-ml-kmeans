"""
estilos.py - diseño visual de la app (despues de la portada).

Solo cambia la apariencia: la logica del modelo sigue en app.py y cluster_utils.py.
- Bola animada (Uiverse.io, dexter-st) grande y difuminada como luz de fondo.
- Tarjetas semitransparentes tipo vidrio.
- Letra elegante (Cormorant Garamond) para titulos e Inter para el resto.
"""
import streamlit as st

# Colores de cada cluster (salen de la bola). Si hubiera mas de 3 clusters se reciclan.
COLORES_CLUSTER = ["#ad5fff", "#d60a47", "#6b5cff", "#f0a35e", "#3fc1c9", "#e86fd0", "#9be15d", "#ffd166"]

_FUENTE = (
    "@import url('https://fonts.googleapis.com/css2?"
    "family=Cormorant+Garamond:wght@300;400&family=Inter:wght@300;400;500&display=swap');"
)

_CSS = """
/* ---------- Fondo: se deja transparente para que se vean las bolas ---------- */
.stApp {
  background-color: #0d0b1a;
  isolation: isolate;
}
[data-testid="stAppViewContainer"], [data-testid="stHeader"], [data-testid="stMain"],
[data-testid="stBottomBlockContainer"] {
  background: transparent !important;
}
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] {
  display: none;
}

/* ---------- Bola grande difuminada (arriba a la derecha) ---------- */
.stApp::before {
  content: "";
  position: fixed;
  width: 560px;
  height: 560px;
  top: -140px;
  right: -150px;
  border-radius: 50%;
  filter: blur(38px);
  opacity: 0.85;
  z-index: -1;
  pointer-events: none;
  animation: bola-grande 6s linear infinite, bola-flotar 10s ease-in-out infinite;
}
@keyframes bola-grande {
  0%   { transform: rotate(90deg);
         box-shadow: 0 31px 62px 0 #fff inset, 0 62px 93px 0 #ad5fff inset, 0 187px 187px 0 #471eec inset; }
  50%  { transform: rotate(270deg);
         box-shadow: 0 31px 62px 0 #fff inset, 0 62px 31px 0 #d60a47 inset, 0 124px 187px 0 #311e80 inset; }
  100% { transform: rotate(450deg);
         box-shadow: 0 31px 62px 0 #fff inset, 0 62px 93px 0 #ad5fff inset, 0 187px 187px 0 #471eec inset; }
}

/* ---------- Bola pequeña difuminada (abajo a la izquierda) ---------- */
.stApp::after {
  content: "";
  position: fixed;
  width: 380px;
  height: 380px;
  bottom: -130px;
  left: -120px;
  border-radius: 50%;
  filter: blur(45px);
  opacity: 0.5;
  z-index: -1;
  pointer-events: none;
  animation: bola-chica 8s linear infinite reverse, bola-flotar 12s ease-in-out infinite reverse;
}
@keyframes bola-chica {
  0%   { transform: rotate(90deg);
         box-shadow: 0 21px 42px 0 #fff inset, 0 42px 63px 0 #ad5fff inset, 0 127px 127px 0 #471eec inset; }
  50%  { transform: rotate(270deg);
         box-shadow: 0 21px 42px 0 #fff inset, 0 42px 21px 0 #d60a47 inset, 0 84px 127px 0 #311e80 inset; }
  100% { transform: rotate(450deg);
         box-shadow: 0 21px 42px 0 #fff inset, 0 42px 63px 0 #ad5fff inset, 0 127px 127px 0 #471eec inset; }
}
@keyframes bola-flotar {
  0%, 100% { translate: 0 0; }
  50%      { translate: 0 40px; }
}

/* ---------- Texto general ---------- */
.stApp, .stApp p, .stApp label, .stApp input, .stApp button {
  font-family: 'Inter', sans-serif;
}

/* ---------- Encabezado ---------- */
.enc-k { font-size: 0.75em; letter-spacing: 0.35em; color: #b9b3d6; margin: 0; }
.enc-h {
  font-family: 'Cormorant Garamond', Georgia, serif;
  font-weight: 300; font-size: 3.2em; letter-spacing: 0.02em; line-height: 1.1;
  color: #ffffff; margin: 0.05em 0 0.15em;
}
.enc-s { font-size: 1em; color: #b9b3d6; margin: 0 0 1.4em; }

/* ---------- Tarjetas tipo vidrio ---------- */
.vidrio {
  background: rgba(26, 22, 48, 0.55);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 14px;
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
}
.kpis { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin-bottom: 1.2em; }
.kpi { padding: 0.8em 1em; }
.kpi p { margin: 0; font-size: 0.72em; letter-spacing: 0.15em; color: #b9b3d6; }
.kpi b { font-weight: 300; font-size: 1.9em; color: #ffffff; }
.etiqueta { font-size: 0.75em; letter-spacing: 0.2em; color: #b9b3d6; margin: 0 0 0.6em; }

/* ---------- Pestañas ---------- */
[data-baseweb="tab-list"] { border-bottom: 1px solid rgba(255, 255, 255, 0.1); gap: 1.5em; }
[data-baseweb="tab"] p { color: #b9b3d6; font-size: 0.95em; }
[data-baseweb="tab"][aria-selected="true"] p { color: #ffffff; }

/* ---------- Formulario ---------- */
[data-testid="stForm"] {
  background: rgba(26, 22, 48, 0.55);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 14px;
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
}
[data-testid="stNumberInput"] input { background: rgba(13, 11, 26, 0.7); }

/* ---------- Botones: borde blanco tipo pildora (Clasificar y Descargar) ---------- */
[data-testid="stElementContainer"]:has([data-testid="stFormSubmitButton"]) {
  width: 100% !important;
  display: flex;
  justify-content: center;
}
[data-testid="stFormSubmitButton"] { display: flex; justify-content: center; margin: 0 auto; }
[data-testid="stFormSubmitButton"] button, .stDownloadButton button {
  min-width: 200px;
  background: transparent !important;
  color: #ffffff !important;
  border: 1px solid #ffffff !important;
  border-radius: 999px !important;
  font-weight: 300;
  letter-spacing: 0.25em;
  text-transform: uppercase;
  transition: background 0.25s ease;
}
[data-testid="stFormSubmitButton"] button:hover, .stDownloadButton button:hover {
  background: rgba(255, 255, 255, 0.10) !important;
}

/* ---------- Subir archivo y desplegables ---------- */
[data-testid="stFileUploaderDropzone"], [data-testid="stExpander"] details {
  background: rgba(26, 22, 48, 0.55) !important;
  border: 1px solid rgba(255, 255, 255, 0.08) !important;
  border-radius: 14px !important;
}

/* ---------- Tarjeta de resultado ---------- */
.resultado { padding: 1.1em 1.2em; }
.res-fila { display: flex; align-items: center; gap: 0.6em; margin-bottom: 0.4em; }
.punto { width: 14px; height: 14px; border-radius: 50%; flex: none; }
.res-nombre {
  font-family: 'Cormorant Garamond', Georgia, serif;
  font-weight: 400; font-size: 1.9em; line-height: 1.1; color: #ffffff; margin: 0;
}
.res-desc { font-size: 0.9em; color: #b9b3d6; margin: 0 0 1.1em; line-height: 1.5; }
.barra-fila {
  display: grid; grid-template-columns: 6em 1fr 3em; align-items: center; gap: 0.6em;
  font-size: 0.8em; color: #b9b3d6; margin-bottom: 0.45em;
}
.barra { height: 8px; border-radius: 4px; background: rgba(255, 255, 255, 0.1); overflow: hidden; }
.barra i { display: block; height: 100%; border-radius: 4px; }
.vacio { padding: 2em 1.4em; text-align: center; color: #b9b3d6; }
.vacio p { margin: 0; }
.vacio .grande {
  font-family: 'Cormorant Garamond', Georgia, serif; font-size: 1.6em; color: #ffffff; margin-bottom: 0.3em;
}

/* ---------- Tarjetas de clusters ---------- */
.clusters { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; margin: 0.4em 0 1em; }
.cl { padding: 0.9em 1em; border-top: 3px solid; }
.cl .pct { font-size: 0.75em; letter-spacing: 0.1em; color: #ffffff; }
.cl h4 {
  font-family: 'Cormorant Garamond', Georgia, serif;
  font-weight: 400; font-size: 1.45em; color: #ffffff; margin: 0.15em 0 0.25em; padding: 0;
}
.cl p { margin: 0; font-size: 0.82em; color: #b9b3d6; line-height: 1.6; }
"""


def aplicar() -> None:
    """Inyecta el CSS del diseño. Se llama una vez al inicio de app.py."""
    st.html(f"<style>{_FUENTE}</style><style>{_CSS}</style>")


def color_cluster(c: int) -> str:
    return COLORES_CLUSTER[int(c) % len(COLORES_CLUSTER)]

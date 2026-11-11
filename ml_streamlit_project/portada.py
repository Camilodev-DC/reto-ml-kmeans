"""
portada.py - pantalla de inicio que se muestra ANTES de la app.

La animacion del circulo viene de Uiverse.io (autor: dexter-st).
Mientras el usuario no presione "Iniciar", app.py se detiene aqui (st.stop()).
El fondo oscuro lo pone el tema de .streamlit/config.toml.
"""
import html

import streamlit as st

# ---------------------------------------------------------------------------
# Lo que se puede cambiar facilmente
# ---------------------------------------------------------------------------
TITULO = "Segmentación de K-Means"
TEXTO_BOTON = "Iniciar"
ESCALA_CIRCULO = 2.7    # 1 = tamaño original de Uiverse (180 px); 2.7 ≈ 486 px

# ---------------------------------------------------------------------------
# Estilos de la portada
# ---------------------------------------------------------------------------
_TAM = round(180 * ESCALA_CIRCULO)   # tamaño final del circulo en px

# Fuente elegante del titulo (Google Fonts). Sin internet se usa una serif normal.
_FUENTE = (
    "@import url('https://fonts.googleapis.com/css2?"
    "family=Cormorant+Garamond:wght@300;400&family=Inter:wght@300;400&display=swap');"
)

_CSS_PORTADA = f"""
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] {{
  display: none;
}}
.portada {{
  display: flex;
  justify-content: center;
  padding-top: 3vh;
  padding-bottom: 1vh;
}}
/* Escena: el circulo flotando y el titulo cruzandolo */
.escena {{
  position: relative;
  width: {_TAM}px;
  height: {_TAM}px;
  max-width: 80vw;
  max-height: 80vw;
  animation: flotar 4s ease-in-out infinite;
}}
@keyframes flotar {{
  0%, 100% {{ transform: translateY(0); }}
  50%      {{ transform: translateY(-18px); }}
}}
.escena .loader-wrapper {{
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%) scale({ESCALA_CIRCULO});
}}
/* Titulo en una sola linea horizontal, mas ancho que la bola */
.titulo-portada {{
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  z-index: 2;
  margin: 0;
  padding: 0;
  white-space: nowrap;
  text-align: center;
  font-family: 'Cormorant Garamond', Georgia, serif;
  font-weight: 300;
  font-size: clamp(34px, 5.2vw, 72px);
  letter-spacing: 0.06em;
  line-height: 1;
  color: #ffffff;
  text-shadow: 0 2px 18px rgba(13, 11, 26, 0.8);
}}
/* Boton "Iniciar": centrado, transparente, borde blanco, forma de pildora */
[data-testid="stElementContainer"]:has(.stButton) {{
  width: 100% !important;
  display: flex;
  justify-content: center;
}}
.stButton {{
  display: flex;
  justify-content: center;
  margin: 0 auto;
}}
.stButton button {{
  width: auto;
  min-width: 200px;
  background: transparent !important;
  color: #ffffff !important;
  border: 1px solid #ffffff !important;
  border-radius: 999px !important;
  padding: 0.65em 1.5em !important;
  font-family: 'Inter', sans-serif;
  font-weight: 300;
  letter-spacing: 0.25em;
  text-transform: uppercase;
  transition: background 0.25s ease;
}}
.stButton button:hover {{
  background: rgba(255, 255, 255, 0.10) !important;
}}
.stButton button:focus:not(:active) {{
  border-color: #ffffff !important;
  color: #ffffff !important;
}}
"""

# ---------------------------------------------------------------------------
# CSS de Uiverse.io (dexter-st): circulo animado, sin cambios.
# (Se quitaron solo las reglas de las letras, porque ya no se usan.)
# ---------------------------------------------------------------------------
_CSS_LOADER = """
.loader-wrapper {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 180px;
  height: 180px;
  font-family: "Inter", sans-serif;
  font-size: 1.2em;
  font-weight: 300;
  color: white;
  border-radius: 50%;
  background-color: transparent;
  user-select: none;
}

.loader {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  aspect-ratio: 1 / 1;
  border-radius: 50%;
  background-color: transparent;
  animation: loader-rotate 2s linear infinite;
  z-index: 0;
}

@keyframes loader-rotate {
  0% {
    transform: rotate(90deg);
    box-shadow:
      0 10px 20px 0 #fff inset,
      0 20px 30px 0 #ad5fff inset,
      0 60px 60px 0 #471eec inset;
  }
  50% {
    transform: rotate(270deg);
    box-shadow:
      0 10px 20px 0 #fff inset,
      0 20px 10px 0 #d60a47 inset,
      0 40px 60px 0 #311e80 inset;
  }
  100% {
    transform: rotate(450deg);
    box-shadow:
      0 10px 20px 0 #fff inset,
      0 20px 30px 0 #ad5fff inset,
      0 60px 60px 0 #471eec inset;
  }
}
"""


def mostrar_portada() -> None:
    """Muestra la portada y detiene la app hasta que el usuario presione el boton."""
    if st.session_state.get("entro_a_la_app", False):
        return  # ya entro: se sigue con el resto de app.py

    st.html(f"""
    <style>{_FUENTE}</style>
    <style>{_CSS_PORTADA}{_CSS_LOADER}</style>
    <div class="portada">
      <div class="escena">
        <div class="loader-wrapper"><div class="loader"></div></div>
        <h1 class="titulo-portada">{html.escape(TITULO)}</h1>
      </div>
    </div>
    """)

    if st.button(TEXTO_BOTON):
        st.session_state["entro_a_la_app"] = True
        st.rerun()

    st.stop()  # no se ejecuta nada mas de app.py mientras se ve la portada

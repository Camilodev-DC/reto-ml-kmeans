"""
cluster_utils.py - motor reutilizable de la Ruta B (clustering con K-Means).

Lo importan el notebook, train.py y app.py.

Las clases de limpieza viven aqui (y no en el notebook) a proposito: joblib
guarda una *referencia* al modulo donde se definio cada clase. Si estuvieran
definidas en el notebook, model.joblib no se podria cargar dentro de Docker.
"""
from __future__ import annotations

import re
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.cluster import KMeans
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    adjusted_rand_score,
    calinski_harabasz_score,
    davies_bouldin_score,
    silhouette_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import MinMaxScaler, OneHotEncoder, RobustScaler, StandardScaler

# ---------------------------------------------------------------------------
# 1. Configuracion: todo lo que se puede elegir
# ---------------------------------------------------------------------------
DEFAULT_CONFIG = {
    # --- Variables ---------------------------------------------------------
    "numeric_features": "auto",     # "auto" o lista de columnas numericas
    "categorical_features": [],     # [] (ninguna), "auto" o lista de columnas
    "log_features": "auto",         # "auto", [] o lista: numericas muy sesgadas a las que se aplica log
    "exclude": [],                  # columnas que nunca deben entrar al modelo
    # --- Limpieza por filas (solo durante el entrenamiento) ---------------
    "drop_duplicates": True,        # elimina filas exactamente repetidas
    "max_missing_row": 0.5,         # elimina filas con mas de este % de faltantes en las variables elegidas
    # --- Criterios del modo "auto" -----------------------------------------
    "max_missing_col": 0.4,         # descarta columnas con mas de este % de faltantes
    "max_categories": 15,           # categoricas con mas niveles se descartan / se agrupan
    "skew_threshold": 1.0,          # asimetria a partir de la cual "auto" aplica log
    # --- Limpieza dentro del pipeline (se repite igual en la app) ---------
    "numeric_imputer": "median",    # median | mean | most_frequent
    "outliers": "iqr",              # iqr | quantile | none  (recorta, no elimina filas)
    "iqr_factor": 1.5,
    "quantiles": [0.01, 0.99],
    "scaler": "standard",           # standard | robust | minmax | none
    "categorical_imputer": "most_frequent",  # most_frequent | constant ("Desconocido")
    "normalize_categories": True,   # " bogotá " y "BOGOTÁ" -> "Bogotá"
    # --- Modelo ------------------------------------------------------------
    "k": "auto",                    # "auto" (mejor silhouette) o un entero
    "k_min": 2,
    "k_max": 8,
    "n_init": 10,
    "random_state": 42,
    "silhouette_sample": 5000,      # muestra para silhouette en datasets grandes
    "min_cluster_pct": 2.0,         # "auto" evita k con clusters de menos de este %
    # --- Interpretacion (si se dejan vacios se generan automaticamente) ---
    "title": "",
    "cluster_names": {},
    "cluster_descriptions": {},
}

_VALID_OPTIONS = {
    "numeric_imputer": {"median", "mean", "most_frequent"},
    "outliers": {"iqr", "quantile", "none"},
    "scaler": {"standard", "robust", "minmax", "none"},
    "categorical_imputer": {"most_frequent", "constant"},
}

NA_STRINGS = {
    "", "na", "n/a", "nan", "null", "none", "-", "--", "?", "nd", "n.d.",
    "s/d", "sin dato", "sin informacion", "sin información", "no aplica",
}


def merge_config(config: dict | None = None) -> dict:
    """Combina la configuracion del usuario con los valores por defecto y la valida."""
    cfg = deepcopy(DEFAULT_CONFIG)
    if config:
        unknown = set(config) - set(cfg)
        if unknown:
            raise ValueError(
                f"Opciones desconocidas en CONFIG: {sorted(unknown)}. "
                f"Opciones validas: {sorted(cfg)}"
            )
        cfg.update(deepcopy(config))
    for key, valid in _VALID_OPTIONS.items():
        if cfg[key] not in valid:
            raise ValueError(f"CONFIG['{key}'] = {cfg[key]!r} no es valido. Use uno de {sorted(valid)}.")
    if cfg["k"] != "auto":
        cfg["k"] = int(cfg["k"])
        if cfg["k"] < 2:
            raise ValueError("CONFIG['k'] debe ser 'auto' o un entero >= 2.")
    cfg["quantiles"] = [float(q) for q in cfg["quantiles"]]
    cfg["cluster_names"] = {int(k): str(v) for k, v in (cfg.get("cluster_names") or {}).items()}
    cfg["cluster_descriptions"] = {
        int(k): str(v) for k, v in (cfg.get("cluster_descriptions") or {}).items()
    }
    return cfg


# ---------------------------------------------------------------------------
# 2. Carga de datos (CSV con , o ; / Excel / URL / archivo subido)
# ---------------------------------------------------------------------------
def load_table(source, name: str | None = None, sheet_name=0) -> pd.DataFrame:
    """Lee CSV o Excel detectando separador y codificacion automaticamente."""
    label = (name or str(source)).lower().split("?")[0]
    if label.endswith((".xlsx", ".xls")):
        df = pd.read_excel(source, sheet_name=sheet_name)
    else:
        df = None
        for encoding in ("utf-8-sig", "latin-1"):
            try:
                if hasattr(source, "seek"):
                    source.seek(0)
                df = pd.read_csv(source, sep=None, engine="python", encoding=encoding)
                break
            except UnicodeDecodeError:
                continue
        if df is None:
            raise ValueError("No se pudo leer el archivo. Use CSV (UTF-8 o Latin-1) o Excel.")
    df.columns = [str(c).strip() for c in df.columns]
    return df


# ---------------------------------------------------------------------------
# 3. Conversion de valores "sucios"
# ---------------------------------------------------------------------------
_NOT_NUMBER = re.compile(r"[^\d,.\-eE+]")


def _parse_number(value) -> float:
    """'1.234,5' -> 1234.5 | '$ 2,000' -> 2000 | '15%' -> 15 | 'n/a' -> NaN."""
    if value is None:
        return np.nan
    if isinstance(value, (bool, np.bool_)):
        return float(value)
    if isinstance(value, (int, float, np.integer, np.floating)):
        return float(value)
    text = str(value).strip()
    if text.lower() in NA_STRINGS:
        return np.nan
    negative = text.startswith("(") and text.endswith(")")
    text = _NOT_NUMBER.sub("", text)
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):          # 1.234,56 (formato colombiano)
            text = text.replace(".", "").replace(",", ".")
        else:                                           # 1,234.56
            text = text.replace(",", "")
    elif "," in text:
        parts = text.split(",")
        if len(parts) == 2 and len(parts[1]) != 3:      # 3,5 -> decimal
            text = text.replace(",", ".")
        else:                                           # 1,234,567 -> miles
            text = text.replace(",", "")
    elif text.count(".") > 1:                           # 1.234.567 -> miles
        text = text.replace(".", "")
    try:
        number = float(text)
    except ValueError:
        return np.nan
    return -number if negative else number


def to_number(values) -> pd.Series:
    """Convierte una columna a float; lo que no sea numero queda como NaN."""
    series = values if isinstance(values, pd.Series) else pd.Series(values)
    if pd.api.types.is_bool_dtype(series) or pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors="coerce").astype(float)
    return series.map(_parse_number).astype(float)


def clean_category(value, normalize: bool = True):
    """Limpia una categoria: espacios, faltantes, '1.0' -> '1' y (opcional) mayusculas."""
    if value is None:
        return np.nan
    try:
        if pd.isna(value):
            return np.nan
    except (TypeError, ValueError):
        pass
    if isinstance(value, (float, np.floating)) and float(value).is_integer():
        value = int(value)
    text = " ".join(str(value).split())
    if text.lower() in NA_STRINGS:
        return np.nan
    return text.capitalize() if normalize else text


def _as_frame(X, columns=None) -> pd.DataFrame:
    if isinstance(X, pd.DataFrame):
        return X
    return pd.DataFrame(np.asarray(X, dtype=object), columns=columns)


# ---------------------------------------------------------------------------
# 4. Transformadores propios (van DENTRO del pipeline)
# ---------------------------------------------------------------------------
class NumericCleaner(BaseEstimator, TransformerMixin):
    """Convierte texto con formato de numero a float ('1.234,5', '$2.000', '15%')."""

    def fit(self, X, y=None):
        frame = _as_frame(X)
        self.columns_ = [str(c) for c in frame.columns]
        return self

    def transform(self, X):
        frame = _as_frame(X, self.columns_)
        if frame.shape[1] == 0:
            return np.empty((len(frame), 0))
        return np.column_stack([to_number(frame[c]).to_numpy(dtype=float) for c in frame.columns])


class CategoricalCleaner(BaseEstimator, TransformerMixin):
    """Convierte cada categoria a texto limpio y unifica los faltantes como NaN."""

    def __init__(self, normalize=True):
        self.normalize = normalize

    def fit(self, X, y=None):
        frame = _as_frame(X)
        self.columns_ = [str(c) for c in frame.columns]
        return self

    def transform(self, X):
        frame = _as_frame(X, self.columns_)
        out = np.empty(frame.shape, dtype=object)
        for j, col in enumerate(frame.columns):
            out[:, j] = [clean_category(v, self.normalize) for v in frame[col].tolist()]
        return out


class SignedLog1p(BaseEstimator, TransformerMixin):
    """log(1 + |x|) conservando el signo: reduce la asimetria de montos e ingresos."""

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        values = np.asarray(X, dtype=float)
        return np.sign(values) * np.log1p(np.abs(values))


class OutlierClipper(BaseEstimator, TransformerMixin):
    """Recorta valores extremos a limites aprendidos en el entrenamiento (no borra filas)."""

    def __init__(self, method="iqr", factor=1.5, quantiles=(0.01, 0.99)):
        self.method = method
        self.factor = factor
        self.quantiles = quantiles

    def fit(self, X, y=None):
        values = np.asarray(X, dtype=float)
        q_low, q_high = np.nanpercentile(values, [q * 100 for q in self.quantiles], axis=0)
        if self.method == "iqr":
            q1, q3 = np.nanpercentile(values, [25, 75], axis=0)
            iqr = q3 - q1
            lower, upper = q1 - self.factor * iqr, q3 + self.factor * iqr
            # Si IQR = 0 (columna casi constante) se usan los cuantiles para no aplanarla
            flat = iqr == 0
            lower = np.where(flat, q_low, lower)
            upper = np.where(flat, q_high, upper)
        else:
            lower, upper = q_low, q_high
        self.lower_ = np.asarray(lower, dtype=float)
        self.upper_ = np.asarray(upper, dtype=float)
        return self

    def transform(self, X):
        return np.clip(np.asarray(X, dtype=float), self.lower_, self.upper_)


# ---------------------------------------------------------------------------
# 5. Diagnostico de columnas y seleccion de variables
# ---------------------------------------------------------------------------
_ID_NAME = re.compile(
    r"(^id$|^id[_\W]|[_\W]id$|^idx|codigo|código|cedula|cédula|documento|^nit$|uuid|^index$|^unnamed)",
    re.IGNORECASE,
)


def _looks_like_date(series: pd.Series) -> bool:
    import warnings
    sample = series.dropna().astype(str).head(200)
    if sample.empty:
        return False
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            parsed = pd.to_datetime(sample, errors="coerce", format="mixed", dayfirst=True)
        except (TypeError, ValueError):
            return False
    return parsed.notna().mean() >= 0.9


def diagnose(df: pd.DataFrame, config: dict | None = None) -> pd.DataFrame:
    """Tabla con tipo detectado, % faltantes, valores unicos y una sugerencia por columna."""
    cfg = merge_config(config)
    rows = []
    n = len(df)
    for col in df.columns:
        series = df[col]
        non_null = int(series.notna().sum())
        missing = 1 - non_null / n if n else 1.0
        n_unique = int(series.nunique(dropna=True))
        skew = np.nan

        if pd.api.types.is_datetime64_any_dtype(series):
            kind = "fecha"
        elif pd.api.types.is_bool_dtype(series):
            kind = "binaria"
        elif pd.api.types.is_numeric_dtype(series):
            kind = "numérica"
        else:
            parsed = to_number(series)
            ok = parsed.notna().sum() / non_null if non_null else 0
            kind = "numérica (texto)" if ok >= 0.9 else "texto"
            if kind == "texto" and _looks_like_date(series):
                kind = "fecha"

        if kind in ("numérica", "numérica (texto)", "binaria"):
            values = to_number(series).dropna()
            if len(values) > 2:
                # asimetria sobre valores recortados al 1%-99% para que un solo atipico no la domine
                low, high = values.quantile([0.01, 0.99])
                skew = float(values.clip(low, high).skew())

        if non_null == 0:
            suggestion, reason = "excluir", "columna vacía"
        elif n_unique <= 1:
            suggestion, reason = "excluir", "valor constante"
        elif missing > cfg["max_missing_col"]:
            suggestion, reason = "excluir", f"{missing:.0%} de faltantes"
        elif kind == "fecha":
            suggestion, reason = "excluir", "fecha (derive variables si las necesita)"
        elif _ID_NAME.search(str(col)):
            suggestion, reason = "excluir", "el nombre parece un identificador"
        elif kind in ("numérica", "numérica (texto)"):
            values = to_number(series).dropna()
            integer_like = bool(np.allclose(values, np.round(values))) if len(values) else False
            consecutive = integer_like and n_unique == non_null and non_null > 20 and values.is_monotonic_increasing
            if consecutive:
                suggestion, reason = "excluir", "enteros consecutivos (parece ID)"
            else:
                suggestion, reason = "numérica", ""
        elif kind == "binaria":
            suggestion, reason = "numérica", "binaria (0/1)"
        else:
            if n_unique == non_null and non_null > 20:
                suggestion, reason = "excluir", "un valor distinto por fila (ID o texto libre)"
            elif n_unique <= cfg["max_categories"]:
                suggestion, reason = "categórica", ""
            else:
                suggestion, reason = "excluir", f"{n_unique} categorías (demasiadas)"

        rows.append({
            "variable": str(col),
            "tipo_detectado": kind,
            "faltantes_%": round(missing * 100, 1),
            "valores_unicos": n_unique,
            "asimetria": round(skew, 2) if not np.isnan(skew) else np.nan,
            "sugerencia": suggestion,
            "motivo": reason,
        })
    return pd.DataFrame(rows)


def resolve_features(df: pd.DataFrame, config: dict | None = None):
    """Devuelve (numericas, categoricas, log) segun CONFIG; 'auto' usa el diagnostico."""
    cfg = merge_config(config)
    diag = diagnose(df, cfg).set_index("variable")
    exclude = {str(c) for c in cfg["exclude"]}

    def pick(value, kind):
        if value == "auto":
            return [c for c in diag.index if diag.loc[c, "sugerencia"] == kind and c not in exclude]
        columns = [str(c) for c in (value or [])]
        missing = [c for c in columns if c not in df.columns]
        if missing:
            raise ValueError(
                f"Estas columnas no existen en el dataset: {missing}.\n"
                f"Columnas disponibles: {list(df.columns)}"
            )
        return [c for c in columns if c not in exclude]

    numeric = pick(cfg["numeric_features"], "numérica")
    categorical = [c for c in pick(cfg["categorical_features"], "categórica") if c not in numeric]

    if cfg["log_features"] == "auto":
        log_features = [
            c for c in numeric
            if diag.loc[c, "asimetria"] > cfg["skew_threshold"] and to_number(df[c]).min() >= 0
        ]
    else:
        log_features = [str(c) for c in (cfg["log_features"] or []) if str(c) in numeric]

    if not numeric and not categorical:
        raise ValueError(
            "No quedó ninguna variable para el modelo. Revise el diagnóstico y escriba "
            "las columnas en CONFIG['numeric_features'] / CONFIG['categorical_features']."
        )
    return numeric, categorical, log_features


def clean_rows(df: pd.DataFrame, numeric, categorical, config: dict | None = None):
    """Limpieza por filas, SOLO para entrenar: duplicados y filas con demasiados faltantes."""
    cfg = merge_config(config)
    data = df.copy()
    report = {"filas_iniciales": int(len(data))}

    if cfg["drop_duplicates"]:
        before = len(data)
        data = data.drop_duplicates()
        report["duplicados_eliminados"] = int(before - len(data))

    parts = []
    if numeric:
        parts.append(data[numeric].apply(to_number))
    if categorical:
        norm = cfg["normalize_categories"]
        parts.append(data[categorical].apply(lambda s: s.map(lambda v: clean_category(v, norm))))
    missing_share = pd.concat(parts, axis=1).isna().mean(axis=1)
    keep = missing_share <= cfg["max_missing_row"]
    report["filas_con_muchos_faltantes"] = int((~keep).sum())

    data = data.loc[keep].reset_index(drop=True)
    report["filas_finales"] = int(len(data))
    if len(data) < 3:
        raise ValueError("Quedan menos de 3 filas después de limpiar. Revise CONFIG['max_missing_row'].")
    return data, report


# ---------------------------------------------------------------------------
# 6. Pipeline: preprocesamiento + K-Means
# ---------------------------------------------------------------------------
def _make_scaler(name):
    return {"standard": StandardScaler(), "robust": RobustScaler(), "minmax": MinMaxScaler(), "none": None}[name]


def _numeric_pipeline(cfg, use_log):
    steps = [
        ("a_numero", NumericCleaner()),
        ("imputar", SimpleImputer(strategy=cfg["numeric_imputer"], keep_empty_features=True)),
    ]
    if use_log:
        steps.append(("log", SignedLog1p()))
    if cfg["outliers"] != "none":
        steps.append(("atipicos", OutlierClipper(
            method=cfg["outliers"], factor=cfg["iqr_factor"], quantiles=tuple(cfg["quantiles"]),
        )))
    scaler = _make_scaler(cfg["scaler"])
    if scaler is not None:
        steps.append(("escalar", scaler))
    return Pipeline(steps)


def build_preprocessor(config, numeric, categorical, log_features) -> ColumnTransformer:
    cfg = merge_config(config)
    plain = [c for c in numeric if c not in log_features]
    transformers = []
    if plain:
        transformers.append(("num", _numeric_pipeline(cfg, use_log=False), plain))
    if log_features:
        transformers.append(("num_log", _numeric_pipeline(cfg, use_log=True), list(log_features)))
    if categorical:
        if cfg["categorical_imputer"] == "constant":
            imputer = SimpleImputer(strategy="constant", fill_value="Desconocido")
        else:
            imputer = SimpleImputer(strategy="most_frequent")
        transformers.append(("cat", Pipeline([
            ("limpiar", CategoricalCleaner(normalize=cfg["normalize_categories"])),
            ("imputar", imputer),
            ("onehot", OneHotEncoder(
                handle_unknown="ignore", max_categories=cfg["max_categories"], sparse_output=False,
            )),
        ]), list(categorical)))
    return ColumnTransformer(transformers, remainder="drop", sparse_threshold=0.0)


def build_model(config, numeric, categorical, log_features, k) -> Pipeline:
    cfg = merge_config(config)
    return Pipeline([
        ("preprocessor", build_preprocessor(cfg, numeric, categorical, log_features)),
        ("cluster", KMeans(n_clusters=int(k), random_state=cfg["random_state"], n_init=cfg["n_init"])),
    ])


# ---------------------------------------------------------------------------
# 7. Eleccion de k y evaluacion
# ---------------------------------------------------------------------------
def _silhouette(X_proc, labels, cfg) -> float:
    if len(np.unique(labels)) < 2:
        return float("nan")
    sample = min(cfg["silhouette_sample"], len(labels))
    return float(silhouette_score(X_proc, labels, sample_size=sample, random_state=cfg["random_state"]))


def evaluate_k(X_proc, config: dict | None = None) -> pd.DataFrame:
    """Prueba k = k_min..k_max y devuelve inercia, silhouette, Davies-Bouldin y Calinski-Harabasz."""
    cfg = merge_config(config)
    n = X_proc.shape[0]
    rows = []
    for k in range(cfg["k_min"], min(cfg["k_max"], n - 1) + 1):
        km = KMeans(n_clusters=k, random_state=cfg["random_state"], n_init=cfg["n_init"]).fit(X_proc)
        labels = km.labels_
        if len(np.unique(labels)) < 2:
            continue
        rows.append({
            "k": k,
            "inercia": float(km.inertia_),
            "silhouette": _silhouette(X_proc, labels, cfg),
            "davies_bouldin": float(davies_bouldin_score(X_proc, labels)),
            "calinski_harabasz": float(calinski_harabasz_score(X_proc, labels)),
            "cluster_min_%": float(np.bincount(labels).min() / n * 100),
        })
    return pd.DataFrame(rows)


def pick_k(k_table: pd.DataFrame, config: dict | None = None) -> int:
    """Mejor silhouette entre los k cuyo cluster mas pequeno no sea diminuto."""
    cfg = merge_config(config)
    if k_table is None or k_table.empty:
        raise ValueError("No se pudo evaluar ningún k. ¿Hay suficientes filas?")
    valid = k_table[k_table["cluster_min_%"] >= cfg["min_cluster_pct"]]
    table = valid if not valid.empty else k_table
    return int(table.loc[table["silhouette"].idxmax(), "k"])


def stability(X_proc, labels, k, config: dict | None = None, repeats=5, fraction=0.8) -> dict:
    """Re-entrena con submuestras del 80% y compara con el modelo final (ARI: 1 = identico)."""
    cfg = merge_config(config)
    rng = np.random.default_rng(cfg["random_state"])
    n = X_proc.shape[0]
    size = max(int(n * fraction), k + 1)
    scores = []
    for i in range(repeats):
        idx = rng.choice(n, size=min(size, n), replace=False)
        km = KMeans(n_clusters=k, random_state=cfg["random_state"] + i + 1, n_init=cfg["n_init"])
        km.fit(X_proc[idx])
        scores.append(adjusted_rand_score(labels, km.predict(X_proc)))
    return {"estabilidad_ari_media": float(np.mean(scores)), "estabilidad_ari_min": float(np.min(scores))}


# ---------------------------------------------------------------------------
# 8. Perfiles e interpretacion automatica
# ---------------------------------------------------------------------------
def cluster_profiles(data, labels, numeric, categorical, normalize=True):
    """Promedios por cluster (unidades originales), z-scores y categoria dominante."""
    labels = np.asarray(labels)
    clusters = sorted(np.unique(labels).tolist())
    counts = pd.Series(labels).value_counts().reindex(clusters)
    profiles = pd.DataFrame(index=pd.Index(clusters, name="cluster"))
    profiles["n_casos"] = counts.values
    profiles["porcentaje"] = (counts.values / len(labels) * 100).round(1)

    z = None
    if numeric:
        num = data[numeric].apply(to_number).reset_index(drop=True)
        means = num.groupby(labels).mean()
        profiles = profiles.join(means.round(3))
        global_std = num.std(ddof=0).replace(0, np.nan)
        z = ((means - num.mean()) / global_std).round(2)

    categorical_info = {}
    for col in categorical:
        cleaned = data[col].map(lambda v: clean_category(v, normalize)).reset_index(drop=True)
        global_share = cleaned.value_counts(normalize=True)
        info = {}
        dominant = []
        for cl in clusters:
            share = cleaned[labels == cl].value_counts(normalize=True)
            if share.empty:
                info[cl] = (None, 0.0, 0.0)
                dominant.append("")
                continue
            mode, mode_share = share.index[0], float(share.iloc[0])
            info[cl] = (mode, mode_share, float(global_share.get(mode, 0.0)))
            dominant.append(f"{mode} ({mode_share:.0%})")
        profiles[f"{col} (más frecuente)"] = dominant
        categorical_info[col] = info
    return profiles, z, categorical_info


def describe_clusters(profiles, z, categorical_info, threshold=0.5, top=3):
    """Genera nombre y descripcion de cada cluster a partir de los datos."""
    names, descriptions = {}, {}
    for cl in profiles.index:
        parts, name_parts = [], []
        if z is not None:
            zc = z.loc[cl].dropna()
            zc = zc.reindex(zc.abs().sort_values(ascending=False).index)
            for feature, value in zc[zc.abs() >= threshold].head(top).items():
                if value > 0:
                    parts.append(f"por encima del promedio en {feature} ({value:+.1f} DE)")
                    name_parts.append(f"↑ {feature}")
                else:
                    parts.append(f"por debajo del promedio en {feature} ({value:+.1f} DE)")
                    name_parts.append(f"↓ {feature}")
        for col, info in categorical_info.items():
            mode, share, global_share = info.get(cl, (None, 0, 0))
            if mode is not None and share - global_share >= 0.15:
                parts.append(f"predomina {col} = {mode} ({share:.0%} vs {global_share:.0%} general)")
                name_parts.append(f"{col}: {mode}")
        n_cases = int(profiles.loc[cl, "n_casos"])
        pct = float(profiles.loc[cl, "porcentaje"])
        body = "; ".join(parts) if parts else "valores cercanos al promedio en todas las variables"
        names[int(cl)] = " · ".join(name_parts[:2]) if name_parts else "Perfil promedio"
        descriptions[int(cl)] = f"{n_cases} casos ({pct:.0f}%): {body[0].upper() + body[1:]}."
    return names, descriptions


# ---------------------------------------------------------------------------
# 9. Entrenamiento completo (lo usan el notebook y train.py)
# ---------------------------------------------------------------------------
def _package_versions() -> dict:
    import sys
    return {
        "python": sys.version.split()[0],
        "scikit-learn": sklearn.__version__,
        "pandas": pd.__version__,
        "numpy": np.__version__,
    }


def train_clustering(df: pd.DataFrame, config: dict | None = None, verbose: bool = True):
    """Ejecuta TODO el flujo y devuelve (artifact, reporte).

    artifact -> se guarda en model.joblib y lo usa app.py
    reporte  -> datos limpios, etiquetas y matrices para graficar en el notebook
    """
    cfg = merge_config(config)
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]

    numeric, categorical, log_features = resolve_features(df, cfg)
    data, cleaning = clean_rows(df, numeric, categorical, cfg)
    features = numeric + categorical
    X = data[features]

    # La tabla de k se calcula siempre: sirve para justificar la eleccion en el README
    X_tmp = build_preprocessor(cfg, numeric, categorical, log_features).fit_transform(X)
    k_table = evaluate_k(X_tmp, cfg)
    k = pick_k(k_table, cfg) if cfg["k"] == "auto" else cfg["k"]
    if k >= len(data):
        raise ValueError(f"k = {k} es demasiado grande para {len(data)} filas.")

    model = build_model(cfg, numeric, categorical, log_features, k)
    labels = model.fit_predict(X)
    X_proc = model[:-1].transform(X)

    metrics = {
        "k": int(k),
        "silhouette": _silhouette(X_proc, labels, cfg),
        "davies_bouldin": float(davies_bouldin_score(X_proc, labels)),
        "calinski_harabasz": float(calinski_harabasz_score(X_proc, labels)),
        "inercia": float(model.named_steps["cluster"].inertia_),
    }
    metrics.update(stability(X_proc, labels, k, cfg))

    profiles, z, categorical_info = cluster_profiles(
        data, labels, numeric, categorical, cfg["normalize_categories"])
    auto_names, auto_descriptions = describe_clusters(profiles, z, categorical_info)
    names = {c: cfg["cluster_names"].get(c, auto_names[c]) for c in auto_names}
    descriptions = {c: cfg["cluster_descriptions"].get(c, auto_descriptions[c]) for c in auto_descriptions}

    numeric_values = data[numeric].apply(to_number) if numeric else pd.DataFrame()
    numeric_stats = {}
    for col in numeric:
        values = numeric_values[col].dropna()
        numeric_stats[col] = {
            "min": float(values.min()), "max": float(values.max()),
            "median": float(values.median()), "mean": float(values.mean()),
            "std": float(values.std(ddof=0)),
            "is_integer": bool(np.allclose(values, np.round(values))),
        }
    category_options, category_defaults = {}, {}
    for col in categorical:
        cleaned = data[col].map(lambda v: clean_category(v, cfg["normalize_categories"])).dropna().astype(str)
        category_options[col] = sorted(cleaned.unique().tolist())
        category_defaults[col] = cleaned.value_counts().index[0]

    artifact = {
        # Claves que usa el app.py de la guia
        "model": model,
        "features": features,
        "numeric_features": numeric,
        "categorical_features": categorical,
        "task": "clustering",
        "cluster_descriptions": descriptions,
        # Informacion extra para una app mas completa y para el README
        "title": cfg["title"] or "Segmentación con K-Means",
        "log_features": log_features,
        "n_clusters": int(k),
        "cluster_names": names,
        "category_options": category_options,
        "category_defaults": category_defaults,
        "numeric_stats": numeric_stats,
        "global_means": {c: numeric_stats[c]["mean"] for c in numeric},
        "profiles": profiles.reset_index().to_dict(orient="records"),
        "metrics": metrics,
        "k_table": k_table.to_dict(orient="records") if not k_table.empty else None,
        "cleaning_report": cleaning,
        "config": cfg,
        "n_rows_train": int(len(data)),
        "versions": _package_versions(),
        "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    report = {
        "data": data, "X": X, "X_proc": X_proc, "labels": labels,
        "k_table": k_table, "profiles": profiles, "z": z,
    }
    if verbose:
        print(f"Variables numéricas ({len(numeric)}): {numeric}")
        print(f"Variables categóricas ({len(categorical)}): {categorical}")
        print(f"Con transformación log: {log_features}")
        print(f"Limpieza: {cleaning}")
        print(f"k = {k} | silhouette = {metrics['silhouette']:.3f} | "
              f"estabilidad (ARI medio) = {metrics['estabilidad_ari_media']:.2f}")
    return artifact, report


# ---------------------------------------------------------------------------
# 10. Utilidades para la app
# ---------------------------------------------------------------------------
def example_case(artifact) -> dict:
    """Caso 'tipico': mediana de cada numerica y categoria mas frecuente."""
    case = {}
    for col in artifact["numeric_features"]:
        s = artifact["numeric_stats"][col]
        case[col] = int(round(s["median"])) if s["is_integer"] else round(s["median"], 4)
    for col in artifact["categorical_features"]:
        case[col] = artifact["category_defaults"][col]
    return case


def out_of_range(artifact, values: dict) -> list:
    """Variables numericas cuyo valor esta fuera del rango visto en entrenamiento."""
    outside = []
    for col in artifact["numeric_features"]:
        s = artifact["numeric_stats"][col]
        v = values.get(col)
        if v is not None and (v < s["min"] or v > s["max"]):
            outside.append(col)
    return outside


def assign_clusters(artifact, df: pd.DataFrame) -> pd.DataFrame:
    """Asigna cluster a todas las filas de un DataFrame nuevo (columnas extra se conservan)."""
    out = df.copy()
    out.columns = [str(c).strip() for c in out.columns]
    missing = [c for c in artifact["features"] if c not in out.columns]
    if missing:
        raise ValueError(f"Faltan columnas: {missing}")
    labels = artifact["model"].predict(out[artifact["features"]])
    out["cluster"] = labels.astype(int)
    out["cluster_nombre"] = [artifact["cluster_names"].get(int(c), "") for c in labels]
    return out


def save_config(config: dict, path) -> None:
    import json
    cfg = merge_config(config)
    cfg["cluster_names"] = {str(k): v for k, v in cfg["cluster_names"].items()}
    cfg["cluster_descriptions"] = {str(k): v for k, v in cfg["cluster_descriptions"].items()}
    Path(path).write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


def load_config(path) -> dict:
    import json
    return merge_config(json.loads(Path(path).read_text(encoding="utf-8")))

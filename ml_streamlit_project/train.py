"""
train.py - reconstruye el modelo de clustering de forma reproducible.

Uso:
    python train.py
    python train.py --data data/otro.csv --config config.json --output model.joblib

Lee el dataset y las decisiones guardadas en config.json (variables, limpieza, k,
nombres de clusters), entrena el pipeline y guarda model.joblib.
"""
import argparse
import sys
from pathlib import Path

import joblib

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

import cluster_utils as cu  # noqa: E402

DATA_PATH = BASE_DIR / "data" / "datos.csv"
CONFIG_PATH = BASE_DIR / "config.json"
MODEL_PATH = BASE_DIR / "model.joblib"


def load_data(path: Path):
    if not Path(path).exists():
        raise FileNotFoundError(
            f"No se encontró el dataset en {path}. Revise el README para saber cómo obtenerlo."
        )
    return cu.load_table(path)


def train_model(df, config: dict):
    # 1. Variables  2. Limpieza  3. Preprocesamiento  4. Entrenar  5. Evaluar  6. Artifact
    artifact, _ = cu.train_clustering(df, config, verbose=True)
    return artifact


def main() -> None:
    parser = argparse.ArgumentParser(description="Entrena el modelo de clustering (Ruta B).")
    parser.add_argument("--data", default=DATA_PATH, type=Path)
    parser.add_argument("--config", default=CONFIG_PATH, type=Path)
    parser.add_argument("--output", default=MODEL_PATH, type=Path)
    args = parser.parse_args()

    config = cu.load_config(args.config) if args.config.exists() else {}
    if not config:
        print("Aviso: no se encontró config.json; se usará la configuración automática.")

    df = load_data(args.data)
    artifact = train_model(df, config)
    joblib.dump(artifact, args.output)

    m = artifact["metrics"]
    print(f"\nModelo guardado en {args.output}")
    print(f"k = {m['k']} | silhouette = {m['silhouette']:.3f} | "
          f"Davies-Bouldin = {m['davies_bouldin']:.3f}")
    for c, name in artifact["cluster_names"].items():
        print(f"  Cluster {c}: {name}")


if __name__ == "__main__":
    main()

# PRs del proyecto final por integrante

Cada carpeta es un PR para el repo [`housing-price-mlops`](https://github.com/crissebasbol/housing-price-mlops): trae los archivos con su ruta dentro del repo y un `PR.md` con los pasos de git, los mensajes de commit, el texto del PR y una sección "Para explicarlo".

## Estado

| PR | Carpeta | Responsable | Depende de | Estado |
|---|---|---|---|---|
| 00 | - | Cristian Organista | - | Fusionado (scripts del clúster); el arreglo de descargas en `/tmp` va en un PR de Cristhian Bolaños |
| 0 | - | Cristhian Bolaños | - | Fusionado (CODEOWNERS y plantilla de PR) |
| 1 | - | Cristhian Bolaños | - | Fusionado (esquema y calidad) |
| 2 | - | Fabián Ramírez | 1 | Fusionado (features y split) |
| 3 | - | Cristian Organista | 1 | Fusionado (drift y decisión) |
| 4 | - | Cristhian Bolaños | 2 | Fusionado (modelo y compuertas) |
| 5 | - | Fabián Ramírez | 3 y 4 | Fusionado (simulación) |
| 6 | - | Cristian Organista | - | Fusionado (base de datos) |
| 7a | `07-plataforma-datos/` | Fabián Ramírez | 6 | Listo para abrir |
| 7b | - | Cristhian Bolaños | 7a | CI: validación de manifiestos y build de MLflow, después del 7a |

## Preparar el entorno (una sola vez)

```bash
git clone git@github.com:crissebasbol/housing-price-mlops.git
cd housing-price-mlops
uv sync                    # instala Python 3.12 y las dependencias del workspace
uvx pre-commit install     # gitleaks y ruff antes de cada commit
```

## Reglas para todos los PRs

- Rama nueva desde `master` actualizado (`git switch master && git pull`), con el nombre que indica cada `PR.md`.
- Antes de hacer push: `uv run ruff check . && uv run ruff format --check . && uv run pytest`.
- Al abrir el PR aparece la plantilla: completar qué cambia, por qué y cómo se probó (el texto está en cada `PR.md`).
- CODEOWNERS pide revisión automáticamente a los otros dos; se necesita una aprobación.
- Fusionar con **"Create a merge commit"** (no squash) y borrar la rama.
- Nunca subir `.env`, kubeconfig, datos ni modelos.

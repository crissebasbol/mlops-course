# PR 6: base de datos RAW, CLEAN y auditoría (Cristian Organista)

No depende de otros PRs. Puede abrirse ya.

## Pasos

```bash
cd housing-price-mlops
git switch master && git pull
git switch -c feature/base-de-datos

# copiar el contenido de este directorio sobre la raíz del repo:
# database/, scripts/create_secrets.sh y .env.example (reemplaza el actual; solo agrega KUBE_CONTEXT)
chmod +x scripts/create_secrets.sh database/init/01_roles.sh
```

Probar los scripts en un Postgres local (no toca el clúster):

```bash
docker run -d --rm --name pg-test -e POSTGRES_USER=postgres -e POSTGRES_DB=housing \
  -e POSTGRES_PASSWORD=t1 -e AIRFLOW_ETL_PASSWORD=t2 -e API_WRITER_PASSWORD=t3 -e APP_READER_PASSWORD=t4 \
  -v "$PWD/database/init:/docker-entrypoint-initdb.d:ro" postgres:16
sleep 15 && docker logs pg-test 2>&1 | grep -E "ERROR|init process complete"
docker exec -e PGPASSWORD=t3 pg-test psql -h 127.0.0.1 -U api_writer -d housing -c "SELECT count(*) FROM clean.properties"
# debe fallar con "permission denied": la API no puede leer CLEAN
docker stop pg-test

kubectl kustomize database   # solo renderiza el YAML, no aplica nada
```

```bash
git add database/init database/k8s database/kustomization.yaml
git commit -m "Schemas raw, clean y audit con roles de mínimo privilegio"
git add scripts/create_secrets.sh .env.example
git commit -m "Script de Secrets desde .env local"
git push -u origin feature/base-de-datos
```

**Título del PR:** `Base de datos RAW, CLEAN y auditoría`

**Qué cambia**

- `database/init/01_roles.sh`: roles `airflow_etl` (escribe raw, clean y audit), `api_writer` (solo inserta inferencias, feedback y acciones de operación) y `app_reader` (solo lectura para Streamlit y Grafana).
- `database/init/02_schema.sql`: schemas `raw`, `clean` y `audit` en la base `housing`:
  - `raw.batches` (cada petición a la API de datos con su huella SHA-256, ciclo, resultado y estado), `raw.properties` (filas originales en JSONB con su estado de calidad), `raw.inference_events` y `raw.inference_feedback`;
  - `clean.properties` (filas validadas y normalizadas con su split, trazables a `raw.batches`);
  - `audit.batch_runs` (decisión y razón por lote), `audit.model_evaluations`, `audit.model_actions` y la vista `audit.replay_accuracy`.
- `database/k8s/`: StatefulSet de Postgres 16 en `nodo-data` con requests y limits, probes `pg_isready`, PVC de 20 Gi y Service.
- `scripts/create_secrets.sh`: crea los Secrets desde un `.env` local que no se versiona, y se niega a correr si el contexto de `kubectl` no es el del `.env` (`KUBE_CONTEXT`).

**Por qué**

RF2 (RAW y CLEAN separados y trazables), RF1 (no reprocesar: índice único sobre la huella de los lotes nuevos), RF8 (registro de inferencias en el dominio RAW), RF4 (tabla de auditoría visible desde Streamlit) y seguridad básica (sin contraseñas en el repo).

**Cómo se probó**

Postgres 16 local con los scripts de init: corren sin errores; cada rol puede hacer lo que debe y falla en lo prohibido; la vista de replay calcula el MAPE en línea; `kubectl kustomize database` renderiza.

## Para explicarlo

- **¿Por qué schemas y no bases separadas?** La trazabilidad RAW → CLEAN es un join por `row_hash`, y en Postgres no se puede hacer join entre bases distintas. La separación se garantiza con permisos: la API ni siquiera puede leer CLEAN.
- **¿Cómo se evita reprocesar un lote?** `raw.batches` tiene un índice único sobre la huella del contenido cuando el lote es nuevo; un lote repetido se registra como `duplicate` apuntando al original.
- **¿Por qué el Secret no está en el repo?** En proyecto_2 estaba versionado con las contraseñas en texto plano. Ahora `create_secrets.sh` lo crea desde un `.env` que nunca se sube.
- **Ojo:** los scripts de init solo corren la primera vez (con el PVC vacío). Si cambia el esquema después, hay que migrar a mano o recrear el PVC.

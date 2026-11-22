# PR 00: scripts del clúster (Cristian Organista)

Primero de todo: con estos scripts se monta el clúster desde cero (las VMs se limpiaron el 21 nov). Puede abrirse en paralelo con el PR 7a. Los scripts se probaron con `shellcheck` y `bash -n`; se prueban de verdad al correrlos en las VMs, y cualquier arreglo que haga falta va como commit en este mismo PR.

## Flujo

1. **En tu computador:** crear la rama con los archivos, hacer push y abrir el PR como **borrador** (*Draft*).
2. **En las VMs:** clonar el repo por HTTPS (es público, no necesita credenciales), cambiarse a la rama y seguir `cluster/README.md`.
3. **Si un script falla:** corregirlo en tu computador, commit y push a la rama; en la VM, `git pull`. Anotar qué pasó y cómo se resolvió (va a la bitácora del README).
4. **Cuando el clúster esté listo:** marcar el PR como listo para revisión y fusionarlo.

## 1. En tu computador

```bash
cd housing-price-mlops
git switch master && git pull
git switch -c feature/cluster

# copiar el contenido de esta carpeta (00-cluster/) sobre la raíz del repo,
# incluidos .gitignore y .pre-commit-config.yaml (reemplazan los actuales)
mkdir -p argocd/install
cp ../mlops-course/taller_6_argo/argocd/install.yaml argocd/install/install.yaml   # ajustar la ruta a tu clon del monorepo
chmod +x cluster/*.sh scripts/port_forward.sh

git add cluster/*.sh cluster/README.md
git update-index --chmod=+x cluster/*.sh
git commit -m "Scripts para montar el clúster con Rancher y RKE2"
git add cluster/local-path-storage.yaml argocd/install/install.yaml .pre-commit-config.yaml
git commit -m "Manifiestos de local-path y Argo CD guardados en el repo"
git add scripts/port_forward.sh .gitignore
git update-index --chmod=+x scripts/port_forward.sh
git commit -m "Port-forwards de las UIs del clúster"
git push -u origin feature/cluster
```

`install.yaml` pesa 2,1 MB: `.pre-commit-config.yaml` lo excluye del límite de archivos grandes.

## 2. En las VMs

```bash
git clone https://github.com/crissebasbol/housing-price-mlops.git ~/housing-price-mlops
cd ~/housing-price-mlops
git switch feature/cluster
```

Y seguir `cluster/README.md` en orden:

| Paso | Dónde | Comando |
|---|---|---|
| Inventario | .106, .105, .92 | `./cluster/inventory.sh` |
| Limpiar restos (si los hay) | .105, .92 | `sudo ./cluster/cleanup_node.sh --yes && sudo reboot` |
| Rancher | .106 | `./cluster/install_rancher.sh` (la primera vez pide reiniciar) |
| Nodos | .105 / .92 | `sudo ./cluster/prepare_node.sh nodo-data` / `nodo-serving` |
| Clúster `housing` | Interfaz de Rancher | Manual (paso 4 del README) |
| kubectl, helm, argocd y kubeconfig | .106 | Paso 5 del README |
| Bootstrap | .106 | `KUBE_CONTEXT=housing ./cluster/bootstrap.sh` |
| Red | .106 | `./cluster/nettest.sh` |
| Argo CD | .106 | `./scripts/port_forward.sh start` y paso 7 del README |
| Secrets | .106 | Paso 8 del README, cuando el PR 7a esté fusionado |

**Capturas para el README** (sin contraseñas ni tokens): clúster `Active` en Rancher, salida de `bootstrap.sh` (nodos con labels y pods de Argo `Running`), `nettest.sh`.

## Texto del PR

**Título:** `Scripts para montar el clúster`

**Qué cambia**

- `cluster/`: scripts idempotentes para montar el clúster desde cero (`inventory.sh`, `cleanup_node.sh`, `install_rancher.sh`, `prepare_node.sh`, `bootstrap.sh`, `nettest.sh`) y `README.md` con el orden, los puertos y el único paso manual (crear el clúster en Rancher).
- `cluster/local-path-storage.yaml` y `argocd/install/install.yaml`: manifiestos de terceros guardados en el repo porque la red bloquea `raw.githubusercontent.com`. A `local-path` se le agregaron `requests`/`limits` y se fijó `busybox:1.36`.
- `scripts/port_forward.sh`: publica las 10 UIs en los puertos 8002-8011 de la .106 y relanza cada forward si el pod se reinicia.

**Por qué**

Reproducibilidad: el enunciado pide evitar acciones manuales no documentadas. Con estos scripts cualquiera puede rearmar el clúster, y el README de entrega los cita en "Cómo reproducir".

**Cómo se probó**

- [x] `shellcheck` y `bash -n` sin advertencias
- [x] `kubeconform` sobre `local-path-storage.yaml`
- [ ] Ejecución en las VMs (completar con lo que pasó)

## Para explicarlo

- **¿Por qué Rancher?** Crea el clúster RKE2 en las otras VMs desde una interfaz web y da un kubeconfig para administrarlo desde la .106, igual que en proyecto_2.
- **¿Por qué `bootstrap.sh` usa `kubectl apply` si el despliegue es con Argo CD?** Argo CD no puede instalarse a sí mismo: el bootstrap (almacenamiento, labels y Argo) es la única aplicación manual. Todo lo demás lo sincroniza Argo desde Git.
- **¿Por qué `cleanup_node.sh` pide `--yes`?** Borra RKE2 y sus datos; la confirmación evita correrlo por error.
- **¿Por qué `bootstrap.sh` revisa el contexto?** Para no aplicar nada en otro clúster por equivocación.

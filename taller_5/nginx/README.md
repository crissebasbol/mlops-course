# Nginx

Proxy inverso y balanceador de carga delante de las réplicas de la API. 

| Servicio | Contenedor      | Puerto host | Para qué sirve                    |
|----------|-----------------|-------------|-----------------------------------|
| `proxy`  | `taller5-nginx` | 8000        | Única entrada pública a la API.   |

## Configuración ([`nginx.conf`](./nginx.conf))

- `resolver 127.0.0.11 valid=5s`: usa el DNS interno de Docker y lo vuelve a
  consultar cada 5 s. Así, al pasar de 1 a 3 réplicas, Nginx las descubre sin
  reiniciarse.
- `upstream api_backend` con `server api:8989 resolve`: el nombre `api` resuelve
  a la IP de cada réplica y Nginx reparte en round robin.
- `keepalive 128` + `Connection ""`: reutiliza conexiones hacia la API en vez de
  abrir una por petición.
- `proxy_next_upstream`: si una réplica falla, reintenta en otra.
- `/nginx_status`: contador de conexiones activas de Nginx, útil para ver si el
  balanceador se acerca a su límite.

## Límite de conexiones (aprendizaje)

Las pruebas se corrieron con el límite de conexiones por defecto de Nginx:
1 proceso con 512 conexiones. Cada petición en curso ocupa 2 (la de Locust y la
de la réplica). Con cientos de usuarios y peticiones haciendo fila, ese límite
se agota y Nginx responde `500`, o deja de aceptar conexiones (`HTTP 0` en
Locust), sin llegar a la API:

```text
[alert] 512 worker_connections are not enough while connecting to upstream,
client: 10.43.97.106, request: "POST /predict HTTP/1.1", upstream: "http://172.20.0.6:8989/predict"
```

Pasó con 300-400 usuarios en la prueba de 1 réplica y con 400 o más en la de 3.
Para revisarlo:

```bash
docker logs taller5-nginx 2>&1 | grep -c "worker_connections are not enough"
```

## Prueba adicional con 4096 conexiones

[`nginx.conf`](./nginx.conf) dimensiona el balanceador explícitamente:

```nginx
worker_processes auto;          # un proceso de Nginx por núcleo
events {
    worker_connections 4096;    # conexiones por proceso
}
```

Las pruebas principales del taller (`run_levels.sh`) se hicieron con el límite
por defecto de 512 descrito arriba. Esta configuración se probó después en una
prueba adicional con 3 réplicas: 1000 usuarios y luego 4100 (detalle en el paso 7
del [README principal](../README.md)). Para aplicarla y comprobar que Nginx la
cargó:

```bash
docker compose restart proxy
docker compose exec proxy nginx -T 2>/dev/null | grep -E "worker_(processes|connections)"
```

Resultados:

- **Con 1000 usuarios ya no hay errores de conexión.** Con 512 conexiones ese
  nivel daba 40 % de fallos (`HTTP 0`). Con 4096 casi no hay fallos y el RPS se
  queda en ~130-150, el techo de las réplicas. Lo que sobra hace fila: el p95
  sube a decenas de segundos.
- **El error vuelve cerca de los 2000 usuarios.** Con 2 conexiones por petición,
  2000 usuarios necesitan ~4000 conexiones, el nuevo límite. Desde ahí Nginx
  responde `500` otra vez (3423 en la prueba).
- **Aparecen errores que antes quedaban ocultos:**
  - `504 Gateway Time-out` (551): peticiones que esperaron más de 60 s, el
    `proxy_read_timeout` por defecto.
  - `502 Bad Gateway` (3474): respuestas inválidas de las réplicas saturadas.
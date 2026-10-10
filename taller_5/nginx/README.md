# Nginx

Proxy inverso y balanceador de carga delante de las réplicas de la API. 

| Servicio | Contenedor      | Puerto host | Para qué sirve                    |
|----------|-----------------|-------------|-----------------------------------|
| `proxy`  | `taller5-nginx` | 8000        | Única entrada pública a la API.   |

## Configuración ([`nginx.conf`](./nginx.conf))

- `worker_processes auto` + `worker_connections 4096`: un proceso de Nginx por
  núcleo, cada uno con hasta 4096 conexiones abiertas. Con `events {}` vacío
  Nginx usa 1 proceso y 512 conexiones, y cada petición en curso ocupa 2 (la de
  Locust y la de la API). En la prueba de 1 réplica con 300-400 usuarios ese
  límite se agotó y Nginx respondió `500` sin pasar la petición a la API:

  ```text
  [alert] 512 worker_connections are not enough while connecting to upstream,
  client: 10.43.97.106, request: "POST /predict HTTP/1.1", upstream: "http://172.20.0.6:8989/predict"
  ```

  Se subió el límite antes de la prueba de 3 réplicas, para que el balanceador no
  sea el cuello de botella. Para revisarlo:
  `docker logs taller5-nginx 2>&1 | grep -c "worker_connections are not enough"`.
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
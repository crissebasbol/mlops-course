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
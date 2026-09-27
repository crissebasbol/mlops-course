"""Codigo del pipeline de Covertype usado por los DAGs.

  config.py         constantes y variables de entorno (fuente, tablas, features, MinIO)
  source_client.py  DataSourceClient: host remoto o source_app, /data y /restart
  database.py       CovertypeDatabase: todo el SQL (crudo, procesado, entrenamiento, log)
  preprocessing.py  CovertypePreprocessor: de filas crudas a filas tipadas
  storage.py        ModelRegistry: modelos versionados en MinIO
  training.py       entrenadores rf y gmm
  tasks.py          las funciones que ejecutan los operadores
"""

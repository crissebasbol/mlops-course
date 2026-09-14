"""Codigo del pipeline de Penguins usado por el DAG.

  config.py        constantes (tablas, features, rutas)
  database.py      PenguinsDatabase: todo el SQL contra postgres-data
  preprocessing.py PenguinsPreprocessor: de datos crudos a datos limpios
  training.py      ModelStore y los entrenadores (rf y gmm)
  tasks.py         las cuatro funciones que ejecutan los PythonOperator
"""

def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_preprocess_devuelve_features(client, vivienda_valida):
    response = client.post("/preprocess", json=vivienda_valida)
    assert response.status_code == 200
    body = response.json()
    assert body["barrio"] == "chapinero"
    assert body["area_por_habitacion"] == 26.67
    assert body["factor_zona"] == 1.20


def test_predict_usa_el_modelo_falso(client, fake_model, vivienda_valida):
    response = client.post("/predict", json=vivienda_valida)
    assert response.status_code == 200
    assert response.json()["precio_estimado_cop"] == 123.0
    assert response.json()["modelo"] == "fake"
    assert len(fake_model.calls) == 1
    assert fake_model.calls[0]["barrio"] == "chapinero"


def test_predict_fuera_de_rango_devuelve_422_y_no_llama_al_modelo(client, fake_model, vivienda_valida):
    response = client.post("/predict", json={**vivienda_valida, "estrato": 9})
    assert response.status_code == 422
    assert response.json()["detail"] == {
        "error": "OutOfRangeError",
        "field": "estrato",
        "message": "estrato debe estar entre 1 y 6, llegó 9",
    }
    assert fake_model.calls == []


def test_preprocess_barrio_vacio_devuelve_422_con_error_propio(client, vivienda_valida):
    response = client.post("/preprocess", json={**vivienda_valida, "barrio": "   "})
    assert response.status_code == 422
    assert response.json()["detail"]["error"] == "EmptyTextError"
    assert response.json()["detail"]["field"] == "barrio"


def test_preprocess_tipo_invalido_devuelve_422(client, vivienda_valida):
    response = client.post("/preprocess", json={**vivienda_valida, "area_m2": "grande"})
    assert response.status_code == 422

import json
import os
import random
from pathlib import Path

import requests
import streamlit as st

API_URL = os.environ.get("API_URL", "http://api:8000")
EXAMPLES = json.loads((Path(__file__).parent / "examples.json").read_text())

AGE_BINS = ["[0-10)", "[10-20)", "[20-30)", "[30-40)", "[40-50)", "[50-60)", "[60-70)", "[70-80)", "[80-90)", "[90-100)"]
DIAG_GROUPS = ["Circulatory", "Respiratory", "Digestive", "Diabetes", "Injury", "Musculoskeletal", "Genitourinary", "Neoplasms", "Other", "Unknown"]
MED = ["No", "Steady", "Up", "Down"]
CATEGORICAL = {
    "race": ["Caucasian", "AfricanAmerican", "Hispanic", "Asian", "Other", "Unknown"],
    "gender": ["Female", "Male"],
    "age": AGE_BINS,
    "admission_type": ["Emergency", "Urgent", "Elective", "Other", "Unknown"],
    "discharge_disposition": ["Home", "Home health", "Transfer", "Other", "Unknown"],
    "admission_source": ["Emergency", "Referral", "Transfer", "Other", "Unknown"],
    "medical_specialty": [
        "InternalMedicine", "Emergency/Trauma", "Family/GeneralPractice", "Cardiology", "Surgery-General",
        "Nephrology", "Orthopedics", "Orthopedics-Reconstructive", "Radiologist", "Other", "Unknown",
    ],
    "diag_1_group": DIAG_GROUPS,
    "diag_2_group": DIAG_GROUPS,
    "diag_3_group": DIAG_GROUPS,
    "max_glu_serum": ["None", "Norm", ">200", ">300"],
    "a1cresult": ["None", "Norm", ">7", ">8"],
    "metformin": MED, "glipizide": MED, "glyburide": MED, "pioglitazone": MED,
    "rosiglitazone": MED, "glimepiride": MED, "insulin": MED,
    "change": ["No", "Ch"],
    "diabetesmed": ["No", "Yes"],
}
NUMERIC = {
    "time_in_hospital": ("Dias hospitalizado", 1, 14),
    "num_lab_procedures": ("Procedimientos de laboratorio", 0, 200),
    "num_procedures": ("Procedimientos (no laboratorio)", 0, 20),
    "num_medications": ("Medicamentos administrados", 0, 150),
    "number_outpatient": ("Visitas ambulatorias (ano previo)", 0, 100),
    "number_emergency": ("Visitas a urgencias (ano previo)", 0, 100),
    "number_inpatient": ("Hospitalizaciones (ano previo)", 0, 50),
    "number_diagnoses": ("Numero de diagnosticos", 1, 20),
    "diabetes_meds_active": ("Medicamentos para diabetes activos", 0, 23),
    "diabetes_meds_changed": ("Medicamentos con cambio de dosis", 0, 23),
}
SECTIONS = {
    "Paciente y admision": ["race", "gender", "age", "admission_type", "admission_source", "discharge_disposition", "medical_specialty"],
    "Estancia y antecedentes": list(NUMERIC),
    "Diagnosticos y laboratorio": ["diag_1_group", "diag_2_group", "diag_3_group", "max_glu_serum", "a1cresult"],
    "Medicamentos": ["metformin", "glipizide", "glyburide", "pioglitazone", "rosiglitazone", "glimepiride", "insulin", "change", "diabetesmed"],
}
CLASS_COLORS = {"NO": "green", ">30": "orange", "<30": "red"}


def load_example(label: str) -> None:
    for key, value in random.choice(EXAMPLES[label]).items():
        st.session_state[key] = value


def api_get(path: str):
    try:
        response = requests.get(f"{API_URL}{path}", timeout=5)
        return response.json() if response.ok else None
    except requests.RequestException:
        return None


def show_validation_errors(response: requests.Response) -> None:
    try:
        detail = response.json().get("detail")
    except ValueError:
        detail = response.text
    if isinstance(detail, list):
        st.error("La API rechazo los datos ingresados:")
        for item in detail:
            field = ".".join(str(p) for p in item.get("loc", []) if p != "body")
            st.markdown(f"- **{field or 'body'}**: {item.get('msg')} (recibido: `{item.get('input')}`)")
    else:
        st.error(f"Error {response.status_code}: {detail}")


def predict(payload: dict) -> None:
    try:
        response = requests.post(f"{API_URL}/predict", json=payload, timeout=10)
    except requests.RequestException as exc:
        st.error(f"No se pudo conectar con la API ({API_URL}): {exc}")
        return

    if response.status_code == 422:
        show_validation_errors(response)
        return
    if not response.ok:
        show_validation_errors(response)
        return

    result = response.json()
    label = result["prediction_label"]
    st.subheader("Resultado")
    st.markdown(f"### :{CLASS_COLORS.get(label, 'blue')}[{result['prediction_description']}]")
    cols = st.columns(4)
    cols[0].metric("Clase", label)
    cols[1].metric("Probabilidad", f"{result['probability']:.1%}")
    cols[2].metric("Modelo", f"v{result['model_version']}", result["model_alias"])
    cols[3].metric("Latencia", f"{result['latency_ms']:.1f} ms")
    st.bar_chart(result["probabilities"])
    with st.expander("Respuesta completa de la API"):
        st.json(result)


st.set_page_config(page_title="Readmision de pacientes diabeticos", layout="wide")
st.title("Prediccion de readmision hospitalaria")
st.caption("Pacientes diabeticos, dataset Diabetes 130-US hospitals. La inferencia se hace solo a traves de la API.")

with st.sidebar:
    st.header("Modelo en produccion")
    info = api_get("/model-info")
    if info is None:
        st.error(f"API no disponible en {API_URL}")
    elif info.get("status") != "loaded":
        st.warning(info.get("detail", "Modelo no cargado"))
    else:
        st.metric("Version", f"v{info['version']}", info["alias"])
        st.write(f"**Nombre:** {info['model_name']}")
        st.write(f"**Tipo:** {info.get('model_type')}")
        st.write(f"**Run:** {info.get('run_name')}")
        metrics = info.get("metrics", {})
        if "val_f1_macro" in metrics:
            st.write(f"**F1 macro (val):** {metrics['val_f1_macro']:.3f}")
        st.caption(f"Cargado: {info.get('loaded_at')} en {info.get('replica')}")

    st.header("Valores de ejemplo")
    st.button("No readmision", on_click=load_example, args=("NO",), use_container_width=True)
    st.button("Readmision tardia (>30)", on_click=load_example, args=(">30",), use_container_width=True)
    st.button("Readmision temprana (<30)", on_click=load_example, args=("<30",), use_container_width=True)

if "race" not in st.session_state:
    load_example("NO")

tab_form, tab_json = st.tabs(["Formulario", "JSON libre"])

with tab_form:
    with st.form("patient"):
        for title, fields in SECTIONS.items():
            st.markdown(f"#### {title}")
            cols = st.columns(4)
            for i, field in enumerate(fields):
                with cols[i % 4]:
                    if field in NUMERIC:
                        label, low, high = NUMERIC[field]
                        st.number_input(label, min_value=low, max_value=high, step=1, key=field)
                    else:
                        st.selectbox(field, CATEGORICAL[field], key=field)
        submitted = st.form_submit_button("Predecir", type="primary")
    if submitted:
        predict({field: st.session_state[field] for fields in SECTIONS.values() for field in fields})

with tab_json:
    st.write("Permite enviar cualquier JSON a `/predict`, por ejemplo con valores invalidos, para ver la validacion de la API.")
    default = json.dumps({field: st.session_state[field] for fields in SECTIONS.values() for field in fields}, indent=2)
    raw = st.text_area("Payload", value=default, height=400)
    if st.button("Enviar JSON"):
        try:
            predict(json.loads(raw))
        except json.JSONDecodeError as exc:
            st.error(f"JSON invalido: {exc}")

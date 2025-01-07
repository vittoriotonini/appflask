from flask import Flask, jsonify, request
from flask_cors import CORS
import requests  
import json
from collections import Counter

app = Flask(__name__)
CORS(app)

# URL del file JSON ospitato su Netlify
json_url = 'https://fanciful-puffpuff-138927.netlify.app'

# Carica i dati JSON dal file remoto (Netlify)
try:
    response = requests.get(json_url)
    response.raise_for_status()  # Verifica se la richiesta ha avuto successo
    dati_catasto = response.json()  # Converte la risposta JSON in un dizionario Python
except (requests.exceptions.RequestException, ValueError) as e:
    print(f"Error: {str(e)}")
    dati_catasto = []

# Quick lookup dictionary for id_C
dati_catasto_dict = {marker['id_C']: marker for marker in dati_catasto}

def error_response(message, status_code):
    return jsonify({"errore": message}), status_code

def round_coordinates(lat, lon):
    """Utility function to round coordinates to 5 decimals."""
    return round(lat, 5), round(lon, 5)

# Route to get marker details by id_C
@app.route('/dettagli_marker/<int:id_C>', methods=['GET'])
def dettagli_marker(id_C):
    marker = dati_catasto_dict.get(id_C)
    return jsonify(marker) if marker else error_response("Dati non trovati", 404)

# Route to get markers by FAMILY and PATRONYMIC
@app.route('/markers_by_family_patronymic', methods=['GET'])
def markers_by_family_patronymic():
    family = request.args.get('family')
    patronymic = request.args.get('patronymic')

    if not family or not patronymic:
        return error_response("Parametri 'family' e 'patronymic' mancanti", 400)

    matching_ids = [
        marker['id_C'] for marker in dati_catasto
        if marker.get('FAMILY') == family and marker.get('PATRONYMIC') == patronymic
    ]

    return jsonify({"matching_ids": matching_ids}) if matching_ids else error_response("Nessun marker trovato con FAMILY e PATRONYMIC specificati", 404)

@app.route('/polygon_details', methods=['GET'])
def polygon_details():
    layer = request.args.get('layer')  # Nome della colonna
    region = request.args.get('region')  # Valore da cercare

    if not layer or not region:
        return error_response("Parametri 'layer' e 'region' mancanti", 400)

    layer_column_map = {
        'Location': 'LOCATION',
        'Quarter': 'QUARTER',
        'Gonf Piviere': 'GONF_PIVIERE'
    }

    column_to_search = layer_column_map.get(layer)
    if not column_to_search:
        return error_response(f"Layer '{layer}' non supportato", 400)

    matching_records = [
        record for record in dati_catasto
        if record.get(column_to_search) == region
    ]

    if not matching_records:
        return error_response("Nessun record trovato per il poligono selezionato", 404)

    # Calcola i dati necessari
    total_population = sum(
        (record.get('BOCCHE_M', 0) + record.get('BOCCHE_U', 0) + record.get('BOCCHE_F', 0) + 1)
        for record in matching_records
    )

    record_count = len(matching_records)
    unique_popoli = {record.get('POPOLO') for record in matching_records if record.get('POPOLO')}
    unique_popoli_count = len(unique_popoli)

    top_ids = []
    if record_count > 5:
        num_ids_to_return = 5 if record_count > 30 else 3
        top_ids = sorted(
            matching_records,
            key=lambda record: record.get('TOTAL_ASSETS', 0),
            reverse=True
        )[:num_ids_to_return]
        top_ids = [record.get('id_C') for record in top_ids]

    top_ids_details = {
        record['id_C']: {
            'NAME': record.get('NAME'),
            'PATRONYMIC': record.get('PATRONYMIC'),
            'FAMILY': record.get('FAMILY'),
            'TOTAL_ASSETS': record.get('TOTAL_ASSETS', 0)
        }
        for record in matching_records if record['id_C'] in top_ids
    }

    occupations = [record.get('OCCUPATION') for record in matching_records if record.get('OCCUPATION')]
    occupation_counts = Counter(occupations)
    most_common_occupation, count = occupation_counts.most_common(1)[0] if occupation_counts else (None, 0)

    # Calcola il numero di occupazioni valide
    occupation_valid_count = sum(1 for record in matching_records if record.get('OCCUPATION'))

    family_assets = {}
    for record in matching_records:
        family = record.get('FAMILY')
        if family:
            family_assets[family] = family_assets.get(family, 0) + record.get('TOTAL_ASSETS', 0)

    richest_family = max(family_assets.items(), key=lambda x: x[1], default=(None, 0))

    details = {
        "popolo": region,
        "record_count": record_count,
        "total_population": total_population,
        "unique_popoli_count": unique_popoli_count,
        "occupation_counts": occupation_counts,
        "most_common_occupation": f"{most_common_occupation} - {count} householders" if most_common_occupation else None,
        "richest_family": f"{richest_family[0]} - {richest_family[1]} florins of assets" if richest_family[0] else None,
        "top_ids": top_ids,
        "top_ids_details": top_ids_details,
        "occupation_valid_count": occupation_valid_count  # Aggiunto qui
    }

    return jsonify(details)

@app.route('/settlement_details', methods=['GET'])
def settlement_details():
    lat = request.args.get('lat', type=float)
    lon = request.args.get('lon', type=float)

    if lat is None or lon is None:
        return error_response("Parametri 'lat' e 'lon' mancanti", 400)

    rounded_lat, rounded_lon = round_coordinates(lat, lon)

    matching_records = [
        record for record in dati_catasto
        if round_coordinates(record.get('LAT', 0), record.get('LONG', 0)) == (rounded_lat, rounded_lon)
    ]

    if not matching_records:
        return error_response("Nessun record trovato per la posizione specificata", 404)

    total_population = sum(
        (record.get('BOCCHE_M', 0) + record.get('BOCCHE_U', 0) + record.get('BOCCHE_F', 0) + 1)
        for record in matching_records
    )

    record_count = len(matching_records)

    occupation_valid_count = sum(1 for record in matching_records if record.get('OCCUPATION'))

    top_ids = []
    if record_count > 5:
        num_ids_to_return = 5 if record_count > 30 else 3
        top_ids = sorted(
            matching_records,
            key=lambda record: record.get('TOTAL_ASSETS', 0),
            reverse=True
        )[:num_ids_to_return]
        top_ids = [record.get('id_C') for record in top_ids]

    top_ids_details = {
        record['id_C']: {
            'NAME': record.get('NAME'),
            'PATRONYMIC': record.get('PATRONYMIC'),
            'FAMILY': record.get('FAMILY'),
            'TOTAL_ASSETS': record.get('TOTAL_ASSETS', 0)
        }
        for record in matching_records if record['id_C'] in top_ids
    }

    occupations = [record.get('OCCUPATION') for record in matching_records if record.get('OCCUPATION')]
    occupation_counts = Counter(occupations)
    most_common_occupation, count = occupation_counts.most_common(1)[0] if occupation_counts else (None, 0)

    family_assets = {}
    for record in matching_records:
        family = record.get('FAMILY')
        if family:
            family_assets[family] = family_assets.get(family, 0) + record.get('TOTAL_ASSETS', 0)

    richest_family = max(family_assets.items(), key=lambda x: x[1], default=(None, 0))

    details = {
    "popolo": matching_records[0].get("POPOLO", "Sconosciuto"),
    "lat": rounded_lat,
    "lon": rounded_lon,
    "record_count": record_count,
    "occupation_valid_count": occupation_valid_count,
    "total_population": total_population,
    "top_ids": top_ids,
    "top_ids_details": top_ids_details,
    "most_common_occupation": f"{most_common_occupation} - {count} householders" if most_common_occupation else None,
    "richest_family": f"{richest_family[0]} - {richest_family[1]} florins of assets" if richest_family[0] else None,
    "occupation_counts": occupation_counts,
    "gonf_piviere": matching_records[0].get("GONF_PIVIERE", None),
    "quarter": matching_records[0].get("QUARTER", None),
    "location": matching_records[0].get("LOCATION", None),
}

    return jsonify(details)

@app.route('/markers_by_election_office_term', methods=['GET'])
def markers_by_election_office_term():
    election = request.args.get('election')
    office = request.args.get('office')
    term = request.args.get('term')

    if not election or not office or not term:
        return error_response("Parametri 'election', 'office' e 'term' mancanti", 400)

    matching_ids = [
        marker['id_C'] for marker in dati_catasto
        if marker.get('ELECTION') == election and marker.get('OFFICE') == office
        and marker.get('TERM') == term and marker.get('ELECTION') == "Elected."
    ]

    return jsonify({"matching_ids": matching_ids}) if matching_ids else error_response("Nessun marker trovato con ELECTION, OFFICE e TERM specificati", 404)

@app.route('/markers_by_family_gonfalone', methods=['GET'])
def markers_by_family_gonfalone():
    family = request.args.get('family')
    gonfalone = request.args.get('gonfalone')
    patronymic = request.args.get('patronymic')
    popolo = request.args.get('popolo')

    if not family or not gonfalone:
        return error_response("Parametri 'family' e 'gonfalone' mancanti", 400)

    matching_ids = [
        marker['id_C'] for marker in dati_catasto
        if marker.get('FAMILY') == family and marker.get('GONF_PIVIERE') == gonfalone and
           (marker.get('PATRONYMIC') != patronymic or (not marker.get('PATRONYMIC') and not patronymic)) and
           (marker.get('POPOLO') != popolo or (not marker.get('POPOLO') and not popolo))
    ]

    return jsonify({"matching_ids": matching_ids}) if matching_ids else error_response("Nessun marker trovato con i criteri specificati", 404)

@app.route('/markers_by_criteria', methods=['GET'])
def markers_by_criteria():
    family = request.args.get('family')
    popolo = request.args.get('popolo')
    patronymic = request.args.get('patronymic')

    if not family or not popolo:
        return error_response("Parametri 'family' e 'popolo' mancanti", 400)

    matching_ids = [
        marker['id_C'] for marker in dati_catasto
        if marker.get('FAMILY') == family and marker.get('POPOLO') == popolo and (
            marker.get('PATRONYMIC') != patronymic or (not marker.get('PATRONYMIC') and not patronymic)
        )
    ]

    return jsonify({"matching_ids": matching_ids}) if matching_ids else error_response("Nessun marker trovato con i criteri specificati", 404)

@app.route('/markers_by_family_quarter', methods=['GET'])
def markers_by_family_quarter():
    family = request.args.get('family')
    quarter = request.args.get('quarter')
    patronymic = request.args.get('patronymic')
    popolo = request.args.get('popolo')
    gonfalone = request.args.get('gonfalone')

    valid_quarters = ["San Gimignano", "Castiglione", "Colle", "Montepulciano"]

    if not family or not quarter or quarter not in valid_quarters:
        return error_response("Parametri 'family' e 'quarter' mancanti o 'quarter' non valido", 400)

    matching_ids = [
        marker['id_C'] for marker in dati_catasto
        if marker.get('FAMILY') == family and marker.get('QUARTER') == quarter and
           (marker.get('PATRONYMIC') != patronymic or (not marker.get('PATRONYMIC') and not patronymic)) and
           (marker.get('POPOLO') != popolo or (not marker.get('POPOLO') and not popolo)) and
           (marker.get('GONF_PIVIERE') != gonfalone or (not marker.get('GONF_PIVIERE') and not gonfalone))
    ]

    return jsonify({"matching_ids": matching_ids}) if matching_ids else error_response("Nessun marker trovato con i criteri specificati", 404)

@app.route('/markers_by_family_location', methods=['GET'])
def markers_by_family_location():
    family = request.args.get('family')
    location = request.args.get('location')
    patronymic = request.args.get('patronymic')
    popolo = request.args.get('popolo')
    gonfalone = request.args.get('gonfalone')

    valid_locations = ["Firenze", "Pisa", "Pistoia", "Arezzo", "Cortona", "Volterra"]

    if not family or not location or location not in valid_locations:
        return error_response("Parametri 'family' e 'location' mancanti o 'location' non valida", 400)

    matching_ids = [
        marker['id_C'] for marker in dati_catasto
        if marker.get('FAMILY') == family and marker.get('LOCATION') == location and
           (marker.get('PATRONYMIC') != patronymic or (not marker.get('PATRONYMIC') and not patronymic)) and
           (marker.get('POPOLO') != popolo or (not marker.get('POPOLO') and not popolo)) and
           (marker.get('GONF_PIVIERE') != gonfalone or (not marker.get('GONF_PIVIERE') and not gonfalone))
    ]

    return jsonify({"matching_ids": matching_ids}) if matching_ids else error_response("Nessun marker trovato con i criteri specificati", 404)

@app.route('/search_family', methods=['GET'])
def search_family():
    # Parametri di ricerca
    name = request.args.get('name', '').strip()
    patronymic = request.args.get('patronymic', '').strip()
    family = request.args.get('family', '').strip()

    # Verifica che almeno uno dei parametri sia presente
    if not (name or patronymic or family):
        return error_response("Inserire almeno un parametro tra NAME, PATRONYMIC e FAMILY", 400)

    # Filtra i dati in base ai parametri forniti
    matching_records = [
        {
            'id_C': marker['id_C'],
            'NAME': marker.get('NAME', 'Sconosciuto'),
            'PATRONYMIC': marker.get('PATRONYMIC', 'Sconosciuto'),
            'FAMILY': marker.get('FAMILY', 'Sconosciuto'),
            'DETAIL': next((marker.get(field) for field in ['POPOLO', 'GONF_PIVIERE', 'QUARTER', 'LOCATION'] if marker.get(field)), 'Nessun dettaglio disponibile')
        }
        for marker in dati_catasto
        if (not name or name.lower() in marker.get('NAME', '').lower()) and
           (not patronymic or patronymic.lower() in marker.get('PATRONYMIC', '').lower()) and
           (not family or family.lower() in marker.get('FAMILY', '').lower())
    ]

    # Restituisci i risultati
    if not matching_records:
        return error_response("Nessun record trovato", 404)

    return jsonify(matching_records)

if __name__ == '__main__':
    app.run(debug=True)

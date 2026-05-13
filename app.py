from flask import Flask, render_template, jsonify, request

app = Flask(__name__)

transactions = [
    {"id": 1, "type": "revenu", "categorie": "Salaire", "montant": 150000, "description": "Salaire Janvier"},
    {"id": 2, "type": "depense", "categorie": "Nourriture", "montant": 25000, "description": "Courses semaine"},
    {"id": 3, "type": "depense", "categorie": "Transport", "montant": 10000, "description": "Bus mensuel"},
    {"id": 4, "type": "depense", "categorie": "Loisirs", "montant": 15000, "description": "Sortie resto"},
    {"id": 5, "type": "revenu", "categorie": "Freelance", "montant": 50000, "description": "Projet web"},
    {"id": 6, "type": "depense", "categorie": "Factures", "montant": 30000, "description": "Electricite"},
]

prochain_id = 7

@app.route("/")
def accueil():
    return render_template("index.html")

@app.route("/api/resume")
def resume():
    total_revenus = sum(t["montant"] for t in transactions if t["type"] == "revenu")
    total_depenses = sum(t["montant"] for t in transactions if t["type"] == "depense")
    solde = total_revenus - total_depenses
    nb_transactions = len(transactions)
    return jsonify({
        "revenus": total_revenus,
        "depenses": total_depenses,
        "solde": solde,
        "nb_transactions": nb_transactions
    })

@app.route("/api/depenses-par-categorie")
def depenses_par_categorie():
    categories = {}
    for t in transactions:
        if t["type"] == "depense":
            cat = t["categorie"]
            if cat in categories:
                categories[cat] += t["montant"]
            else:
                categories[cat] = t["montant"]
    return jsonify({
        "labels": list(categories.keys()),
        "valeurs": list(categories.values())
    })

@app.route("/api/transactions")
def liste_transactions():
    return jsonify(transactions)

@app.route("/api/ajouter", methods=["POST"])
def ajouter():
    global prochain_id
    data = request.get_json()
    nouvelle = {
        "id": prochain_id,
        "type": data["type"],
        "categorie": data["categorie"],
        "montant": int(data["montant"]),
        "description": data["description"]
    }
    transactions.append(nouvelle)
    prochain_id += 1
    return jsonify({"succes": True})

# NOUVEAU : modifier une transaction
@app.route("/api/modifier/<int:id>", methods=["PUT"])
def modifier(id):
    data = request.get_json()
    for t in transactions:
        if t["id"] == id:
            t["type"] = data["type"]
            t["categorie"] = data["categorie"]
            t["montant"] = int(data["montant"])
            t["description"] = data["description"]
            return jsonify({"succes": True})
    return jsonify({"succes": False, "erreur": "Transaction introuvable"})

# NOUVEAU : supprimer une transaction
@app.route("/api/supprimer/<int:id>", methods=["DELETE"])
def supprimer(id):
    global transactions
    transactions = [t for t in transactions if t["id"] != id]
    return jsonify({"succes": True})

if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=5000)
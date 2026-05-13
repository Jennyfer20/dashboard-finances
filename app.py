from flask import Flask, render_template, jsonify, request
import sqlite3

app = Flask(__name__)

def get_db():
    conn = sqlite3.connect("finances.db")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute("""CREATE TABLE IF NOT EXISTS transactions (id INTEGER PRIMARY KEY AUTOINCREMENT, type TEXT NOT NULL, categorie TEXT NOT NULL, montant INTEGER NOT NULL, description TEXT NOT NULL, date_ajout TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    count = conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
    if count == 0:
        demos = [("revenu","Salaire",150000,"Salaire Janvier"),("depense","Nourriture",25000,"Courses semaine"),("depense","Transport",10000,"Bus mensuel"),("depense","Loisirs",15000,"Sortie resto"),("revenu","Freelance",50000,"Projet web"),("depense","Factures",30000,"Electricite")]
        conn.executemany("INSERT INTO transactions (type,categorie,montant,description) VALUES (?,?,?,?)", demos)
    conn.commit()
    conn.close()

init_db()

@app.route("/")
def accueil():
    return render_template("index.html")

@app.route("/api/resume")
def resume():
    conn = get_db()
    revenus = conn.execute("SELECT COALESCE(SUM(montant),0) FROM transactions WHERE type='revenu'").fetchone()[0]
    depenses = conn.execute("SELECT COALESCE(SUM(montant),0) FROM transactions WHERE type='depense'").fetchone()[0]
    nb = conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
    conn.close()
    return jsonify({"revenus":revenus,"depenses":depenses,"solde":revenus-depenses,"nb_transactions":nb})

@app.route("/api/depenses-par-categorie")
def depenses_par_categorie():
    conn = get_db()
    rows = conn.execute("SELECT categorie, SUM(montant) as total FROM transactions WHERE type='depense' GROUP BY categorie").fetchall()
    conn.close()
    return jsonify({"labels":[r["categorie"] for r in rows],"valeurs":[r["total"] for r in rows]})

@app.route("/api/transactions")
def liste_transactions():
    conn = get_db()
    rows = conn.execute("SELECT * FROM transactions ORDER BY id DESC").fetchall()
    conn.close()
    return jsonify([{"id":r["id"],"type":r["type"],"categorie":r["categorie"],"montant":r["montant"],"description":r["description"]} for r in rows])

@app.route("/api/ajouter", methods=["POST"])
def ajouter():
    data = request.get_json()
    conn = get_db()
    conn.execute("INSERT INTO transactions (type,categorie,montant,description) VALUES (?,?,?,?)", (data["type"],data["categorie"],int(data["montant"]),data["description"]))
    conn.commit()
    conn.close()
    return jsonify({"succes":True})

@app.route("/api/modifier/<int:id>", methods=["PUT"])
def modifier(id):
    data = request.get_json()
    conn = get_db()
    conn.execute("UPDATE transactions SET type=?,categorie=?,montant=?,description=? WHERE id=?", (data["type"],data["categorie"],int(data["montant"]),data["description"],id))
    conn.commit()
    conn.close()
    return jsonify({"succes":True})

@app.route("/api/supprimer/<int:id>", methods=["DELETE"])
def supprimer(id):
    conn = get_db()
    conn.execute("DELETE FROM transactions WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return jsonify({"succes":True})

if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=5000)

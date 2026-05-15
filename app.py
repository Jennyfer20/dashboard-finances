from flask import Flask, render_template, jsonify, request, session, redirect
import sqlite3
import hashlib

app = Flask(__name__)
app.secret_key = "budgetlab_secret_key_2024"

def get_db():
    conn = sqlite3.connect("finances.db")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        mot_de_passe TEXT NOT NULL
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        type TEXT NOT NULL,
        categorie TEXT NOT NULL,
        montant INTEGER NOT NULL,
        description TEXT NOT NULL,
        date_ajout TEXT DEFAULT (date('now')),
        FOREIGN KEY (user_id) REFERENCES users(id)
    )""")
    conn.commit()
    conn.close()

init_db()

def hash_mdp(mot_de_passe):
    return hashlib.sha256(mot_de_passe.encode()).hexdigest()

@app.route("/")
def landing():
    return render_template("landing.html")

@app.route("/login")
def login_page():
    return render_template("login.html")

@app.route("/register")
def register_page():
    return render_template("register.html")

@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect("/login")
    return render_template("index.html", user_nom=session["user_nom"])

@app.route("/api/register", methods=["POST"])
def api_register():
    data = request.get_json()
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO users (nom, email, mot_de_passe) VALUES (?, ?, ?)",
            (data["nom"], data["email"], hash_mdp(data["mot_de_passe"]))
        )
        conn.commit()
        user = conn.execute("SELECT * FROM users WHERE email=?", (data["email"],)).fetchone()
        session["user_id"] = user["id"]
        session["user_nom"] = user["nom"]
        conn.close()
        return jsonify({"succes": True})
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({"succes": False, "erreur": "Cet email existe deja"})

@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json()
    conn = get_db()
    user = conn.execute(
        "SELECT * FROM users WHERE email=? AND mot_de_passe=?",
        (data["email"], hash_mdp(data["mot_de_passe"]))
    ).fetchone()
    conn.close()
    if user:
        session["user_id"] = user["id"]
        session["user_nom"] = user["nom"]
        return jsonify({"succes": True})
    return jsonify({"succes": False, "erreur": "Email ou mot de passe incorrect"})

@app.route("/api/logout")
def api_logout():
    session.clear()
    return redirect("/")

@app.route("/api/profil")
def profil():
    if "user_id" not in session:
        return jsonify({"erreur": "Non connecte"}), 401
    conn = get_db()
    user = conn.execute("SELECT nom, email FROM users WHERE id=?", (session["user_id"],)).fetchone()
    conn.close()
    return jsonify({"nom": user["nom"], "email": user["email"]})

@app.route("/api/profil/modifier", methods=["PUT"])
def modifier_profil():
    if "user_id" not in session:
        return jsonify({"erreur": "Non connecte"}), 401
    data = request.get_json()
    conn = get_db()
    try:
        conn.execute("UPDATE users SET nom=?, email=? WHERE id=?",
            (data["nom"], data["email"], session["user_id"]))
        conn.commit()
        session["user_nom"] = data["nom"]
        conn.close()
        return jsonify({"succes": True})
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({"succes": False, "erreur": "Cet email est deja utilise"})

@app.route("/api/profil/mot-de-passe", methods=["PUT"])
def changer_mdp():
    if "user_id" not in session:
        return jsonify({"erreur": "Non connecte"}), 401
    data = request.get_json()
    conn = get_db()
    user = conn.execute("SELECT mot_de_passe FROM users WHERE id=?", (session["user_id"],)).fetchone()
    if user["mot_de_passe"] != hash_mdp(data["ancien"]):
        conn.close()
        return jsonify({"succes": False, "erreur": "Ancien mot de passe incorrect"})
    conn.execute("UPDATE users SET mot_de_passe=? WHERE id=?",
        (hash_mdp(data["nouveau"]), session["user_id"]))
    conn.commit()
    conn.close()
    return jsonify({"succes": True})

@app.route("/api/profil/supprimer", methods=["DELETE"])
def supprimer_compte():
    if "user_id" not in session:
        return jsonify({"erreur": "Non connecte"}), 401
    conn = get_db()
    conn.execute("DELETE FROM transactions WHERE user_id=?", (session["user_id"],))
    conn.execute("DELETE FROM users WHERE id=?", (session["user_id"],))
    conn.commit()
    conn.close()
    session.clear()
    return jsonify({"succes": True})

@app.route("/api/resume")
def resume():
    if "user_id" not in session:
        return jsonify({"erreur": "Non connecte"}), 401
    conn = get_db()
    uid = session["user_id"]
    revenus = conn.execute("SELECT COALESCE(SUM(montant),0) FROM transactions WHERE type='revenu' AND user_id=?", (uid,)).fetchone()[0]
    depenses = conn.execute("SELECT COALESCE(SUM(montant),0) FROM transactions WHERE type='depense' AND user_id=?", (uid,)).fetchone()[0]
    nb = conn.execute("SELECT COUNT(*) FROM transactions WHERE user_id=?", (uid,)).fetchone()[0]
    conn.close()
    return jsonify({"revenus":revenus,"depenses":depenses,"solde":revenus-depenses,"nb_transactions":nb})

@app.route("/api/depenses-par-categorie")
def depenses_par_categorie():
    if "user_id" not in session:
        return jsonify({"erreur": "Non connecte"}), 401
    conn = get_db()
    rows = conn.execute("SELECT categorie, SUM(montant) as total FROM transactions WHERE type='depense' AND user_id=? GROUP BY categorie", (session["user_id"],)).fetchall()
    conn.close()
    return jsonify({"labels":[r["categorie"] for r in rows],"valeurs":[r["total"] for r in rows]})

@app.route("/api/transactions")
def liste_transactions():
    if "user_id" not in session:
        return jsonify({"erreur": "Non connecte"}), 401
    uid = session["user_id"]
    categorie = request.args.get("categorie", "")
    date_debut = request.args.get("date_debut", "")
    date_fin = request.args.get("date_fin", "")
    conn = get_db()
    query = "SELECT * FROM transactions WHERE user_id=?"
    params = [uid]
    if categorie:
        query += " AND categorie=?"
        params.append(categorie)
    if date_debut:
        query += " AND date_ajout>=?"
        params.append(date_debut)
    if date_fin:
        query += " AND date_ajout<=?"
        params.append(date_fin)
    query += " ORDER BY id DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return jsonify([{"id":r["id"],"type":r["type"],"categorie":r["categorie"],"montant":r["montant"],"description":r["description"],"date_ajout":r["date_ajout"]} for r in rows])

@app.route("/api/categories")
def categories():
    if "user_id" not in session:
        return jsonify({"erreur": "Non connecte"}), 401
    conn = get_db()
    rows = conn.execute("SELECT DISTINCT categorie FROM transactions WHERE user_id=?", (session["user_id"],)).fetchall()
    conn.close()
    return jsonify([r["categorie"] for r in rows])

@app.route("/api/ajouter", methods=["POST"])
def ajouter():
    if "user_id" not in session:
        return jsonify({"erreur": "Non connecte"}), 401
    data = request.get_json()
    conn = get_db()
    conn.execute("INSERT INTO transactions (user_id,type,categorie,montant,description) VALUES (?,?,?,?,?)", (session["user_id"],data["type"],data["categorie"],int(data["montant"]),data["description"]))
    conn.commit()
    conn.close()
    return jsonify({"succes":True})

@app.route("/api/modifier/<int:id>", methods=["PUT"])
def modifier(id):
    if "user_id" not in session:
        return jsonify({"erreur": "Non connecte"}), 401
    data = request.get_json()
    conn = get_db()
    conn.execute("UPDATE transactions SET type=?,categorie=?,montant=?,description=? WHERE id=? AND user_id=?", (data["type"],data["categorie"],int(data["montant"]),data["description"],id,session["user_id"]))
    conn.commit()
    conn.close()
    return jsonify({"succes":True})

@app.route("/api/supprimer/<int:id>", methods=["DELETE"])
def supprimer(id):
    if "user_id" not in session:
        return jsonify({"erreur": "Non connecte"}), 401
    conn = get_db()
    conn.execute("DELETE FROM transactions WHERE id=? AND user_id=?", (id,session["user_id"]))
    conn.commit()
    conn.close()
    return jsonify({"succes":True})

if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=5000)
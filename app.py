from flask import Flask, render_template, jsonify, request, session, redirect, send_file
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
        mot_de_passe TEXT NOT NULL,
        role TEXT DEFAULT 'comptable',
        mode TEXT DEFAULT 'perso'
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS employes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom TEXT NOT NULL,
        poste TEXT NOT NULL,
        departement TEXT NOT NULL,
        salaire_base INTEGER NOT NULL,
        email TEXT,
        telephone TEXT,
        date_embauche TEXT DEFAULT (date('now')),
        actif INTEGER DEFAULT 1
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
    conn.execute("""CREATE TABLE IF NOT EXISTS salaires (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        employe_id INTEGER NOT NULL,
        mois TEXT NOT NULL,
        montant INTEGER NOT NULL,
        bonus INTEGER DEFAULT 0,
        deductions INTEGER DEFAULT 0,
        net_paye INTEGER NOT NULL,
        statut TEXT DEFAULT 'en_attente',
        date_paiement TEXT,
        FOREIGN KEY (employe_id) REFERENCES employes(id)
    )""")
    conn.commit()
    conn.close()

init_db()

def hash_mdp(mot_de_passe):
    return hashlib.sha256(mot_de_passe.encode()).hexdigest()

# === PAGES ===
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
    return render_template("index.html", user_nom=session["user_nom"], user_mode=session.get("user_mode", "perso"))
# === AUTH API ===
@app.route("/api/register", methods=["POST"])
def api_register():
    data = request.get_json()
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO users (nom, email, mot_de_passe, mode) VALUES (?, ?, ?, ?)",
            (data["nom"], data["email"], hash_mdp(data["mot_de_passe"]), data.get("mode", "perso")))
        conn.commit()
        user = conn.execute("SELECT * FROM users WHERE email=?", (data["email"],)).fetchone()
        session["user_id"] = user["id"]
        session["user_nom"] = user["nom"] 
        session["user_mode"] = user["mode"]
        conn.close()
        return jsonify({"succes": True})
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({"succes": False, "erreur": "Cet email existe deja"})

@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json()
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE email=? AND mot_de_passe=?",
        (data["email"], hash_mdp(data["mot_de_passe"]))).fetchone()
    conn.close()
    if user:
        session["user_id"] = user["id"]
        session["user_nom"] = user["nom"]
        session["user_mode"] = user["mode"]
        return jsonify({"succes": True})
    return jsonify({"succes": False, "erreur": "Email ou mot de passe incorrect"})

@app.route("/api/logout")
def api_logout():
    session.clear()
    return redirect("/")

# === PROFIL API ===
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

# === DASHBOARD API ===
@app.route("/api/dashboard")
def api_dashboard():
    if "user_id" not in session:
        return jsonify({"erreur": "Non connecte"}), 401
    conn = get_db()
    uid = session["user_id"]
    revenus = conn.execute("SELECT COALESCE(SUM(montant),0) FROM transactions WHERE type='revenu' AND user_id=?", (uid,)).fetchone()[0]
    depenses = conn.execute("SELECT COALESCE(SUM(montant),0) FROM transactions WHERE type='depense' AND user_id=?", (uid,)).fetchone()[0]
    factures = conn.execute("SELECT COALESCE(SUM(montant),0) FROM transactions WHERE type='facture' AND user_id=?", (uid,)).fetchone()[0]
    nb_trans = conn.execute("SELECT COUNT(*) FROM transactions WHERE user_id=?", (uid,)).fetchone()[0]
    nb_employes = conn.execute("SELECT COUNT(*) FROM employes WHERE actif=1").fetchone()[0]
    masse_salariale = conn.execute("SELECT COALESCE(SUM(salaire_base),0) FROM employes WHERE actif=1").fetchone()[0]
    salaires_payes = conn.execute("SELECT COALESCE(SUM(net_paye),0) FROM salaires WHERE statut='paye'").fetchone()[0]
    conn.close()
    return jsonify({
        "revenus": revenus,
        "depenses": depenses,
        "factures": factures,
        "benefice": revenus + factures - depenses - salaires_payes,
        "nb_transactions": nb_trans,
        "nb_employes": nb_employes,
        "masse_salariale": masse_salariale,
        "salaires_payes": salaires_payes
    })

@app.route("/api/depenses-par-categorie")
def depenses_par_categorie():
    if "user_id" not in session:
        return jsonify({"erreur": "Non connecte"}), 401
    conn = get_db()
    rows = conn.execute("SELECT categorie, SUM(montant) as total FROM transactions WHERE type='depense' AND user_id=? GROUP BY categorie", (session["user_id"],)).fetchall()
    conn.close()
    return jsonify({"labels":[r["categorie"] for r in rows],"valeurs":[r["total"] for r in rows]})

@app.route("/api/revenus-par-mois")
def revenus_par_mois():
    if "user_id" not in session:
        return jsonify({"erreur": "Non connecte"}), 401
    conn = get_db()
    rows = conn.execute("""SELECT substr(date_ajout,1,7) as mois, 
        SUM(CASE WHEN type='revenu' OR type='facture' THEN montant ELSE 0 END) as revenus,
        SUM(CASE WHEN type='depense' THEN montant ELSE 0 END) as depenses
        FROM transactions WHERE user_id=? GROUP BY mois ORDER BY mois""", (session["user_id"],)).fetchall()
    conn.close()
    return jsonify({
        "mois": [r["mois"] for r in rows],
        "revenus": [r["revenus"] for r in rows],
        "depenses": [r["depenses"] for r in rows]
    })

# === TRANSACTIONS API ===
@app.route("/api/transactions")
def liste_transactions():
    if "user_id" not in session:
        return jsonify({"erreur": "Non connecte"}), 401
    uid = session["user_id"]
    type_filtre = request.args.get("type", "")
    categorie = request.args.get("categorie", "")
    date_debut = request.args.get("date_debut", "")
    date_fin = request.args.get("date_fin", "")
    conn = get_db()
    query = "SELECT * FROM transactions WHERE user_id=?"
    params = [uid]
    if type_filtre:
        query += " AND type=?"
        params.append(type_filtre)
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
    conn.execute("INSERT INTO transactions (user_id,type,categorie,montant,description) VALUES (?,?,?,?,?)",
        (session["user_id"],data["type"],data["categorie"],int(data["montant"]),data["description"]))
    conn.commit()
    conn.close()
    return jsonify({"succes":True})

@app.route("/api/modifier/<int:id>", methods=["PUT"])
def modifier(id):
    if "user_id" not in session:
        return jsonify({"erreur": "Non connecte"}), 401
    data = request.get_json()
    conn = get_db()
    conn.execute("UPDATE transactions SET type=?,categorie=?,montant=?,description=? WHERE id=? AND user_id=?",
        (data["type"],data["categorie"],int(data["montant"]),data["description"],id,session["user_id"]))
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

# === EMPLOYES API ===
@app.route("/api/employes")
def liste_employes():
    if "user_id" not in session:
        return jsonify({"erreur": "Non connecte"}), 401
    conn = get_db()
    rows = conn.execute("SELECT * FROM employes ORDER BY nom").fetchall()
    conn.close()
    return jsonify([{"id":r["id"],"nom":r["nom"],"poste":r["poste"],"departement":r["departement"],
        "salaire_base":r["salaire_base"],"email":r["email"],"telephone":r["telephone"],
        "date_embauche":r["date_embauche"],"actif":r["actif"]} for r in rows])

@app.route("/api/employes/ajouter", methods=["POST"])
def ajouter_employe():
    if "user_id" not in session:
        return jsonify({"erreur": "Non connecte"}), 401
    data = request.get_json()
    conn = get_db()
    conn.execute("INSERT INTO employes (nom,poste,departement,salaire_base,email,telephone) VALUES (?,?,?,?,?,?)",
        (data["nom"],data["poste"],data["departement"],int(data["salaire_base"]),data.get("email",""),data.get("telephone","")))
    conn.commit()
    conn.close()
    return jsonify({"succes":True})

@app.route("/api/employes/modifier/<int:id>", methods=["PUT"])
def modifier_employe(id):
    if "user_id" not in session:
        return jsonify({"erreur": "Non connecte"}), 401
    data = request.get_json()
    conn = get_db()
    conn.execute("UPDATE employes SET nom=?,poste=?,departement=?,salaire_base=?,email=?,telephone=? WHERE id=?",
        (data["nom"],data["poste"],data["departement"],int(data["salaire_base"]),data.get("email",""),data.get("telephone",""),id))
    conn.commit()
    conn.close()
    return jsonify({"succes":True})

@app.route("/api/employes/supprimer/<int:id>", methods=["DELETE"])
def supprimer_employe(id):
    if "user_id" not in session:
        return jsonify({"erreur": "Non connecte"}), 401
    conn = get_db()
    conn.execute("UPDATE employes SET actif=0 WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return jsonify({"succes":True})

# === SALAIRES API ===
@app.route("/api/salaires")
def liste_salaires():
    if "user_id" not in session:
        return jsonify({"erreur": "Non connecte"}), 401
    mois = request.args.get("mois", "")
    conn = get_db()
    query = """SELECT s.*, e.nom as employe_nom, e.poste as employe_poste 
        FROM salaires s JOIN employes e ON s.employe_id=e.id"""
    params = []
    if mois:
        query += " WHERE s.mois=?"
        params.append(mois)
    query += " ORDER BY s.id DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return jsonify([{"id":r["id"],"employe_id":r["employe_id"],"employe_nom":r["employe_nom"],
        "employe_poste":r["employe_poste"],"mois":r["mois"],"montant":r["montant"],
        "bonus":r["bonus"],"deductions":r["deductions"],"net_paye":r["net_paye"],
        "statut":r["statut"],"date_paiement":r["date_paiement"]} for r in rows])

@app.route("/api/salaires/generer", methods=["POST"])
def generer_salaires():
    if "user_id" not in session:
        return jsonify({"erreur": "Non connecte"}), 401
    data = request.get_json()
    mois = data["mois"]
    conn = get_db()
    existe = conn.execute("SELECT COUNT(*) FROM salaires WHERE mois=?", (mois,)).fetchone()[0]
    if existe > 0:
        conn.close()
        return jsonify({"succes": False, "erreur": "Les salaires de ce mois existent deja"})
    employes = conn.execute("SELECT * FROM employes WHERE actif=1").fetchall()
    for e in employes:
        net = e["salaire_base"]
        conn.execute("INSERT INTO salaires (employe_id,mois,montant,bonus,deductions,net_paye) VALUES (?,?,?,0,0,?)",
            (e["id"], mois, e["salaire_base"], net))
    conn.commit()
    conn.close()
    return jsonify({"succes": True, "nb": len(employes)})

@app.route("/api/salaires/payer/<int:id>", methods=["PUT"])
def payer_salaire(id):
    if "user_id" not in session:
        return jsonify({"erreur": "Non connecte"}), 401
    conn = get_db()
    conn.execute("UPDATE salaires SET statut='paye', date_paiement=date('now') WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return jsonify({"succes": True})

@app.route("/api/salaires/payer-tous", methods=["PUT"])
def payer_tous_salaires():
    if "user_id" not in session:
        return jsonify({"erreur": "Non connecte"}), 401
    data = request.get_json()
    conn = get_db()
    conn.execute("UPDATE salaires SET statut='paye', date_paiement=date('now') WHERE mois=? AND statut='en_attente'", (data["mois"],))
    conn.commit()
    conn.close()
    return jsonify({"succes": True})

@app.route("/api/salaires/modifier/<int:id>", methods=["PUT"])
def modifier_salaire(id):
    if "user_id" not in session:
        return jsonify({"erreur": "Non connecte"}), 401
    data = request.get_json()
    bonus = int(data.get("bonus", 0))
    deductions = int(data.get("deductions", 0))
    montant = int(data["montant"])
    net = montant + bonus - deductions
    conn = get_db()
    conn.execute("UPDATE salaires SET montant=?,bonus=?,deductions=?,net_paye=? WHERE id=?",
        (montant, bonus, deductions, net, id))
    conn.commit()
    conn.close()
    return jsonify({"succes": True})
# API : generer PDF fiche de paie
@app.route("/api/salaires/pdf/<int:id>")
def pdf_salaire(id):
    if "user_id" not in session:
        return redirect("/login")
    conn = get_db()
    sal = conn.execute("""SELECT s.*, e.nom as employe_nom, e.poste as employe_poste, 
        e.departement as employe_dept, e.email as employe_email
        FROM salaires s JOIN employes e ON s.employe_id=e.id WHERE s.id=?""", (id,)).fetchone()
    conn.close()
    if not sal:
        return jsonify({"erreur": "Fiche introuvable"}), 404

    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    import io

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    elements = []

    # Titre
    titre_style = ParagraphStyle('titre', parent=styles['Title'], fontSize=24, textColor=colors.HexColor('#3b82f6'), spaceAfter=10)
    elements.append(Paragraph("BudgetLab", titre_style))
    elements.append(Paragraph("Fiche de paie", styles['Title']))
    elements.append(Spacer(1, 20))

    # Infos employe
    info_style = ParagraphStyle('info', parent=styles['Normal'], fontSize=12, spaceAfter=5)
    elements.append(Paragraph("<b>Employe :</b> " + sal["employe_nom"], info_style))
    elements.append(Paragraph("<b>Poste :</b> " + sal["employe_poste"], info_style))
    elements.append(Paragraph("<b>Departement :</b> " + sal["employe_dept"], info_style))
    elements.append(Paragraph("<b>Email :</b> " + (sal["employe_email"] or ""), info_style))
    elements.append(Paragraph("<b>Periode :</b> " + sal["mois"], info_style))
    elements.append(Spacer(1, 20))

    # Tableau salaire
    data = [
        ["Description", "Montant (FCFA)"],
        ["Salaire de base", "{:,}".format(sal["montant"]).replace(",", " ")],
        ["Bonus", "{:,}".format(sal["bonus"]).replace(",", " ")],
        ["Deductions", "-{:,}".format(sal["deductions"]).replace(",", " ")],
        ["", ""],
        ["NET A PAYER", "{:,}".format(sal["net_paye"]).replace(",", " ")],
    ]

    table = Table(data, colWidths=[10*cm, 6*cm])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3b82f6')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('GRID', (0, 0), (-1, -2), 0.5, colors.HexColor('#e2e8f0')),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#f0fdf4')),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, -1), (-1, -1), 14),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 30))

    # Statut
    statut_text = "PAYE" if sal["statut"] == "paye" else "EN ATTENTE"
    statut_color = '#10b981' if sal["statut"] == "paye" else '#f59e0b'
    statut_style = ParagraphStyle('statut', parent=styles['Normal'], fontSize=14, textColor=colors.HexColor(statut_color))
    elements.append(Paragraph("<b>Statut : " + statut_text + "</b>", statut_style))
    if sal["date_paiement"]:
        elements.append(Paragraph("Date de paiement : " + sal["date_paiement"], info_style))

    elements.append(Spacer(1, 40))
    footer_style = ParagraphStyle('footer', parent=styles['Normal'], fontSize=9, textColor=colors.grey)
    elements.append(Paragraph("Document genere par BudgetLab - Gestion financiere d'entreprise", footer_style))

    doc.build(elements)
    buffer.seek(0)

    filename = "fiche_paie_" + sal["employe_nom"].replace(" ", "_") + "_" + sal["mois"] + ".pdf"
    return send_file(buffer, as_attachment=True, download_name=filename, mimetype='application/pdf')

if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=5000)
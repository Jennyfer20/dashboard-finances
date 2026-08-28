import csv
import functools
import hashlib
import io
import os
import re
from datetime import date, timedelta

from flask import (Flask, Response, render_template, jsonify, request, session,
                   redirect, send_file)
from werkzeug.security import check_password_hash, generate_password_hash

from db import get_db, IntegrityError

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static"),
)

# La cle signe les cookies de session : si elle fuite, n'importe qui peut forger
# une session. Elle vient donc uniquement de l'environnement, jamais du code.
_secret = os.environ.get("SECRET_KEY", "").strip()
if not _secret:
    raise RuntimeError(
        "SECRET_KEY n'est pas definie. En local, renseigne-la dans .env ; "
        "sur Vercel, dans Settings > Environment Variables."
    )
app.secret_key = _secret

# En production le cookie ne doit jamais transiter en clair.
_en_production = bool(os.environ.get("VERCEL") or os.environ.get("RENDER"))
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=_en_production,
    PERMANENT_SESSION_LIFETIME=timedelta(days=7),
    MAX_CONTENT_LENGTH=1024 * 1024,
)

LIMITE_TENTATIVES = 10
FENETRE_TENTATIVES = 15  # minutes


class DonneesInvalides(Exception):
    """Saisie refusee : renvoyee en 400 plutot qu'en erreur 500."""


@app.after_request
def _entetes_securite(reponse):
    reponse.headers["X-Content-Type-Options"] = "nosniff"
    reponse.headers["X-Frame-Options"] = "DENY"
    reponse.headers["Referrer-Policy"] = "same-origin"
    reponse.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' https://cdn.jsdelivr.net https://unpkg.com 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    )
    if _en_production:
        reponse.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return reponse


@app.errorhandler(DonneesInvalides)
def _erreur_donnees(err):
    return jsonify({"succes": False, "erreur": str(err)}), 400


def connexion_requise(vue):
    """Refuse l'acces aux visiteurs non authentifies."""

    @functools.wraps(vue)
    def enveloppe(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({"erreur": "Non connecte"}), 401
        return vue(*args, **kwargs)

    return enveloppe


def est_admin(conn, uid):
    """Le role est relu en base : une session ouverte avant une retrogradation
    ne doit pas conserver les droits."""
    ligne = conn.execute("SELECT role FROM users WHERE id=? AND actif=1", (uid,)).fetchone()
    return bool(ligne) and ligne["role"] == "admin"


def admin_requis(vue):
    """Reserve la vue aux administrateurs, verification faite cote serveur."""

    @functools.wraps(vue)
    def enveloppe(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({"erreur": "Non connecte"}), 401
        conn = get_db()
        autorise = est_admin(conn, session["user_id"])
        conn.close()
        if not autorise:
            return jsonify({"erreur": "Acces reserve aux administrateurs"}), 403
        return vue(*args, **kwargs)

    return enveloppe


def journaliser(conn, action, cible="", detail=""):
    conn.execute(
        "INSERT INTO journal_admin (admin_id, admin_email, action, cible, detail) "
        "VALUES (?, ?, ?, ?, ?)",
        (session["user_id"], session.get("user_email", ""), action, cible, detail))


def corps_json():
    donnees = request.get_json(silent=True)
    if not isinstance(donnees, dict):
        raise DonneesInvalides("Requete invalide")
    return donnees


def texte(donnees, cle, maxi=200, obligatoire=True, defaut=""):
    valeur = donnees.get(cle, defaut)
    valeur = "" if valeur is None else str(valeur).strip()
    if obligatoire and not valeur:
        raise DonneesInvalides("Le champ '%s' est obligatoire." % cle)
    if len(valeur) > maxi:
        raise DonneesInvalides("Le champ '%s' depasse %d caracteres." % (cle, maxi))
    return valeur


def entier(donnees, cle, mini=0, maxi=10 ** 12):
    brut = donnees.get(cle, "")
    try:
        valeur = int(str(brut).strip())
    except (TypeError, ValueError):
        raise DonneesInvalides("Le champ '%s' doit etre un nombre entier." % cle)
    if valeur < mini or valeur > maxi:
        raise DonneesInvalides("Le champ '%s' est hors des valeurs autorisees." % cle)
    return valeur


def email_valide(valeur):
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", valeur):
        raise DonneesInvalides("Adresse email invalide.")
    return valeur.lower()


def mot_de_passe_valide(valeur):
    if len(valeur) < 8:
        raise DonneesInvalides("Le mot de passe doit contenir au moins 8 caracteres.")
    if len(valeur) > 200:
        raise DonneesInvalides("Mot de passe trop long.")
    return valeur


def mois_valide(valeur):
    if not re.fullmatch(r"\d{4}-\d{2}", valeur):
        raise DonneesInvalides("Mois invalide (format attendu : AAAA-MM).")
    return valeur


def date_valide(valeur):
    """Filtre de date : chaine vide acceptee, sinon format AAAA-MM-JJ."""
    if valeur and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", valeur):
        raise DonneesInvalides("Date invalide (format attendu : AAAA-MM-JJ).")
    return valeur


DEVISES = ("FCFA", "EUR", "USD", "GBP", "CAD", "CHF", "MAD", "TND", "XOF", "XAF")


def devise_utilisateur(conn, uid):
    ligne = conn.execute("SELECT devise FROM users WHERE id=?", (uid,)).fetchone()
    return (ligne["devise"] if ligne else None) or "FCFA"


def normaliser_categorie(conn, uid, categorie):
    """Reutilise l'orthographe deja employee par l'utilisateur.

    Sans cela, "Loyer" et "loyer" comptent comme deux categories distinctes
    dans les graphiques et les budgets.
    """
    existante = conn.execute(
        "SELECT categorie FROM transactions WHERE user_id=? AND LOWER(categorie)=LOWER(?) LIMIT 1",
        (uid, categorie)).fetchone()
    if existante:
        return existante["categorie"]
    existante = conn.execute(
        "SELECT categorie FROM budgets WHERE user_id=? AND LOWER(categorie)=LOWER(?) LIMIT 1",
        (uid, categorie)).fetchone()
    if existante:
        return existante["categorie"]
    return categorie


def mois_precedent(reference):
    return (reference.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")


def appliquer_recurrences(conn, uid):
    """Cree les transactions des echeances arrivees a terme.

    Il n'y a pas de tache planifiee en serverless : le rattrapage se fait a la
    consultation du tableau de bord, sur les 12 derniers mois au maximum.
    """
    aujourdhui = date.today()
    lignes = conn.execute("SELECT * FROM recurrences WHERE user_id=? AND actif=1", (uid,)).fetchall()
    creees = 0
    for r in lignes:
        deja_fait = r["dernier_genere"] or ""
        echeances = []
        curseur = aujourdhui.replace(day=1)
        for _ in range(12):
            cle = curseur.strftime("%Y-%m")
            if cle <= deja_fait:
                break
            echeance = curseur.replace(day=min(r["jour_mois"], 28))
            if echeance <= aujourdhui:
                echeances.append((cle, echeance))
            curseur = (curseur - timedelta(days=1)).replace(day=1)
        for cle, echeance in sorted(echeances):
            conn.execute(
                "INSERT INTO transactions (user_id,type,categorie,montant,description,date_ajout) "
                "VALUES (?,?,?,?,?,?)",
                (uid, r["type"], r["categorie"], r["montant"], r["description"],
                 echeance.strftime("%Y-%m-%d")))
            creees += 1
        if echeances:
            conn.execute("UPDATE recurrences SET dernier_genere=? WHERE id=? AND user_id=?",
                         (max(cle for cle, _ in echeances), r["id"], uid))
    if creees:
        conn.commit()
    return creees


def cellule_csv(valeur):
    """Neutralise les valeurs qu'un tableur interpreterait comme une formule."""
    texte_valeur = "" if valeur is None else str(valeur)
    return "'" + texte_valeur if texte_valeur[:1] in ("=", "+", "-", "@") else texte_valeur


def adresse_ip():
    entete = request.headers.get("X-Forwarded-For", "")
    return (entete.split(",")[0].strip() or request.remote_addr or "inconnue")[:100]


def hash_mdp(mot_de_passe):
    return generate_password_hash(mot_de_passe)


def verifier_mdp(hash_stocke, mot_de_passe):
    """Retourne (valide, format_obsolete).

    Les comptes anterieurs a la migration stockent un SHA-256 non sale : on
    l'accepte une derniere fois, puis on le remplace par un hachage scrypt.
    """
    if not hash_stocke:
        return False, False
    if re.fullmatch(r"[0-9a-fA-F]{64}", hash_stocke):
        ancien = hashlib.sha256(mot_de_passe.encode()).hexdigest()
        return ancien == hash_stocke.lower(), True
    return check_password_hash(hash_stocke, mot_de_passe), False


def tentatives_recentes(conn, email, ip):
    return conn.execute(
        "SELECT COUNT(*) FROM tentatives_connexion "
        "WHERE moment > now() - interval '%d minutes' AND (email=? OR ip=?)" % FENETRE_TENTATIVES,
        (email, ip),
    ).fetchone()[0]


def enregistrer_echec(conn, email, ip):
    conn.execute("INSERT INTO tentatives_connexion (email, ip) VALUES (?, ?)", (email, ip))
    conn.execute("DELETE FROM tentatives_connexion WHERE moment < now() - interval '1 day'")
    conn.commit()


def ouvrir_session(user):
    session.permanent = True
    session["user_id"] = user["id"]
    session["user_email"] = user["email"]
    session["user_role"] = user["role"]
    session["user_nom"] = user["nom"]
    session["user_mode"] = user["mode"]
    session["user_nom_entreprise"] = user["nom_entreprise"] or ""


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
    conn = get_db()
    admin = est_admin(conn, session["user_id"])
    conn.close()
    return render_template("index.html", user_nom=session["user_nom"],
                           user_mode=session.get("user_mode", "perso"), est_admin=admin)

@app.route("/api/register", methods=["POST"])
def api_register():
    data = corps_json()
    nom = texte(data, "nom", 100)
    email = email_valide(texte(data, "email", 200))
    mot_de_passe = mot_de_passe_valide(texte(data, "mot_de_passe", 200))
    mode = texte(data, "mode", 20, obligatoire=False, defaut="perso")
    if mode not in ("perso", "entreprise"):
        mode = "perso"
    nom_entreprise = texte(data, "nom_entreprise", 150, obligatoire=False)
    conn = get_db()
    try:
        user = conn.execute(
            "INSERT INTO users (nom, email, mot_de_passe, mode, nom_entreprise) "
            "VALUES (?, ?, ?, ?, ?) RETURNING *",
            (nom, email, hash_mdp(mot_de_passe), mode, nom_entreprise)).fetchone()
        conn.commit()
        ouvrir_session(user)
        conn.close()
        return jsonify({"succes": True})
    except IntegrityError:
        conn.rollback()
        conn.close()
        return jsonify({"succes": False, "erreur": "Cet email existe deja"})

@app.route("/api/login", methods=["POST"])
def api_login():
    data = corps_json()
    email = texte(data, "email", 200).lower()
    mot_de_passe = texte(data, "mot_de_passe", 200)
    ip = adresse_ip()
    conn = get_db()
    # Sans plafond, un script peut essayer des mots de passe indefiniment.
    if tentatives_recentes(conn, email, ip) >= LIMITE_TENTATIVES:
        conn.close()
        return jsonify({"succes": False,
                        "erreur": "Trop de tentatives. Reessaie dans %d minutes." % FENETRE_TENTATIVES}), 429
    user = conn.execute("SELECT * FROM users WHERE LOWER(email)=?", (email,)).fetchone()
    valide, format_obsolete = verifier_mdp(user["mot_de_passe"], mot_de_passe) if user else (False, False)
    if not valide:
        enregistrer_echec(conn, email, ip)
        conn.close()
        return jsonify({"succes": False, "erreur": "Email ou mot de passe incorrect"}), 401
    if not user["actif"]:
        conn.close()
        return jsonify({"succes": False,
                        "erreur": "Ce compte a ete suspendu. Contactez l'administrateur."}), 403
    if format_obsolete:
        conn.execute("UPDATE users SET mot_de_passe=? WHERE id=?",
                     (hash_mdp(mot_de_passe), user["id"]))
    conn.execute("DELETE FROM tentatives_connexion WHERE email=? OR ip=?", (email, ip))
    conn.commit()
    ouvrir_session(user)
    conn.close()
    return jsonify({"succes": True})

@app.route("/api/logout", methods=["POST"])
def api_logout():
    session.clear()
    return jsonify({"succes": True})

@app.route("/api/profil")
@connexion_requise
def profil():
    conn = get_db()
    user = conn.execute("SELECT nom, email, devise FROM users WHERE id=?",
                        (session["user_id"],)).fetchone()
    conn.close()
    return jsonify({"nom": user["nom"], "email": user["email"],
                    "devise": user["devise"] or "FCFA"})

@app.route("/api/profil/modifier", methods=["PUT"])
@connexion_requise
def modifier_profil():
    data = corps_json()
    nom = texte(data, "nom", 100)
    email = email_valide(texte(data, "email", 200))
    devise = texte(data, "devise", 10, obligatoire=False, defaut="FCFA").upper() or "FCFA"
    if devise not in DEVISES:
        raise DonneesInvalides("Devise non prise en charge.")
    conn = get_db()
    try:
        conn.execute("UPDATE users SET nom=?, email=?, devise=? WHERE id=?",
                     (nom, email, devise, session["user_id"]))
        conn.commit()
        session["user_nom"] = nom
        conn.close()
        return jsonify({"succes": True})
    except IntegrityError:
        conn.rollback()
        conn.close()
        return jsonify({"succes": False, "erreur": "Cet email est deja utilise"})

@app.route("/api/profil/mot-de-passe", methods=["PUT"])
@connexion_requise
def changer_mdp():
    data = corps_json()
    ancien = texte(data, "ancien", 200)
    nouveau = mot_de_passe_valide(texte(data, "nouveau", 200))
    conn = get_db()
    user = conn.execute("SELECT mot_de_passe FROM users WHERE id=?", (session["user_id"],)).fetchone()
    valide, _ = verifier_mdp(user["mot_de_passe"], ancien)
    if not valide:
        conn.close()
        return jsonify({"succes": False, "erreur": "Ancien mot de passe incorrect"})
    conn.execute("UPDATE users SET mot_de_passe=? WHERE id=?", (hash_mdp(nouveau), session["user_id"]))
    conn.commit()
    conn.close()
    return jsonify({"succes": True})

@app.route("/api/profil/supprimer", methods=["DELETE"])
@connexion_requise
def supprimer_compte():
    conn = get_db()
    uid = session["user_id"]
    # L'ordre respecte les cles etrangeres : salaires, puis employes, puis users.
    conn.execute("DELETE FROM budgets WHERE user_id=?", (uid,))
    conn.execute("DELETE FROM recurrences WHERE user_id=?", (uid,))
    conn.execute("DELETE FROM salaires WHERE user_id=?", (uid,))
    conn.execute("DELETE FROM employes WHERE user_id=?", (uid,))
    conn.execute("DELETE FROM transactions WHERE user_id=?", (uid,))
    conn.execute("DELETE FROM users WHERE id=?", (uid,))
    conn.commit()
    conn.close()
    session.clear()
    return jsonify({"succes": True})

@app.route("/api/dashboard")
@connexion_requise
def api_dashboard():
    conn = get_db()
    uid = session["user_id"]
    nouvelles = appliquer_recurrences(conn, uid)
    revenus = conn.execute("SELECT COALESCE(SUM(montant),0) FROM transactions WHERE type='revenu' AND user_id=?", (uid,)).fetchone()[0]
    depenses = conn.execute("SELECT COALESCE(SUM(montant),0) FROM transactions WHERE type='depense' AND user_id=?", (uid,)).fetchone()[0]
    factures = conn.execute("SELECT COALESCE(SUM(montant),0) FROM transactions WHERE type='facture' AND user_id=?", (uid,)).fetchone()[0]
    nb_trans = conn.execute("SELECT COUNT(*) FROM transactions WHERE user_id=?", (uid,)).fetchone()[0]
    nb_employes = conn.execute("SELECT COUNT(*) FROM employes WHERE actif=1 AND user_id=?", (uid,)).fetchone()[0]
    masse_salariale = conn.execute("SELECT COALESCE(SUM(salaire_base),0) FROM employes WHERE actif=1 AND user_id=?", (uid,)).fetchone()[0]
    salaires_payes = conn.execute("SELECT COALESCE(SUM(net_paye),0) FROM salaires WHERE statut='paye' AND user_id=?", (uid,)).fetchone()[0]
    devise = devise_utilisateur(conn, uid)
    conn.close()
    return jsonify({"revenus": revenus, "depenses": depenses, "factures": factures,
        "benefice": revenus + factures - depenses - salaires_payes,
        "nb_transactions": nb_trans, "nb_employes": nb_employes,
        "masse_salariale": masse_salariale, "salaires_payes": salaires_payes,
        "devise": devise, "recurrences_creees": nouvelles})

@app.route("/api/depenses-par-categorie")
@connexion_requise
def depenses_par_categorie():
    conn = get_db()
    rows = conn.execute("SELECT categorie, SUM(montant) as total FROM transactions WHERE type='depense' AND user_id=? GROUP BY categorie", (session["user_id"],)).fetchall()
    conn.close()
    return jsonify({"labels":[r["categorie"] for r in rows],"valeurs":[r["total"] for r in rows]})

@app.route("/api/revenus-par-mois")
@connexion_requise
def revenus_par_mois():
    conn = get_db()
    rows = conn.execute("""SELECT substr(date_ajout,1,7) as mois,
        SUM(CASE WHEN type='revenu' OR type='facture' THEN montant ELSE 0 END) as revenus,
        SUM(CASE WHEN type='depense' THEN montant ELSE 0 END) as depenses
        FROM transactions WHERE user_id=? GROUP BY mois ORDER BY mois""", (session["user_id"],)).fetchall()
    conn.close()
    return jsonify({"mois":[r["mois"] for r in rows],"revenus":[r["revenus"] for r in rows],"depenses":[r["depenses"] for r in rows]})

@app.route("/api/transactions")
@connexion_requise
def liste_transactions():
    uid = session["user_id"]
    type_filtre = texte(request.args, "type", 20, obligatoire=False)
    categorie = texte(request.args, "categorie", 100, obligatoire=False)
    date_debut = date_valide(texte(request.args, "date_debut", 10, obligatoire=False))
    date_fin = date_valide(texte(request.args, "date_fin", 10, obligatoire=False))
    recherche = texte(request.args, "q", 100, obligatoire=False)
    page = max(1, entier({"page": request.args.get("page", 1)}, "page", mini=1, maxi=100000))
    par_page = min(200, max(5, entier({"n": request.args.get("par_page", 25)}, "n", mini=5, maxi=200)))

    conditions = "FROM transactions WHERE user_id=?"
    params = [uid]
    if type_filtre: conditions += " AND type=?"; params.append(type_filtre)
    if categorie: conditions += " AND categorie=?"; params.append(categorie)
    if date_debut: conditions += " AND date_ajout>=?"; params.append(date_debut)
    if date_fin: conditions += " AND date_ajout<=?"; params.append(date_fin)
    if recherche:
        conditions += " AND (description ILIKE ? OR categorie ILIKE ?)"
        motif = "%" + recherche + "%"
        params += [motif, motif]

    conn = get_db()
    total = conn.execute("SELECT COUNT(*) " + conditions, params).fetchone()[0]
    rows = conn.execute(
        "SELECT * " + conditions + " ORDER BY date_ajout DESC, id DESC LIMIT ? OFFSET ?",
        params + [par_page, (page - 1) * par_page]).fetchall()
    conn.close()
    pages = max(1, -(-total // par_page))
    return jsonify({
        "transactions": [{"id":r["id"],"type":r["type"],"categorie":r["categorie"],
                          "montant":r["montant"],"description":r["description"],
                          "date_ajout":r["date_ajout"]} for r in rows],
        "total": total, "page": min(page, pages), "pages": pages, "par_page": par_page})

@app.route("/api/transactions/export.csv")
@connexion_requise
def exporter_transactions():
    uid = session["user_id"]
    conn = get_db()
    devise = devise_utilisateur(conn, uid)
    rows = conn.execute(
        "SELECT date_ajout, type, categorie, montant, description FROM transactions "
        "WHERE user_id=? ORDER BY date_ajout DESC, id DESC", (uid,)).fetchall()
    conn.close()
    tampon = io.StringIO()
    # Point-virgule et BOM : Excel en configuration francaise ouvre le fichier
    # directement, sans passer par l'assistant d'importation.
    graveur = csv.writer(tampon, delimiter=";", lineterminator="\r\n")
    graveur.writerow(["Date", "Type", "Categorie", "Montant (%s)" % devise, "Description"])
    for r in rows:
        graveur.writerow([cellule_csv(r["date_ajout"]), cellule_csv(r["type"]),
                          cellule_csv(r["categorie"]), r["montant"],
                          cellule_csv(r["description"])])
    contenu = "\ufeff" + tampon.getvalue()
    nom = "transactions_%s.csv" % date.today().strftime("%Y-%m-%d")
    return Response(contenu, mimetype="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="%s"' % nom})

@app.route("/api/categories")
@connexion_requise
def categories():
    conn = get_db()
    rows = conn.execute(
        "SELECT categorie FROM transactions WHERE user_id=? "
        "UNION SELECT categorie FROM budgets WHERE user_id=? ORDER BY categorie",
        (session["user_id"], session["user_id"])).fetchall()
    conn.close()
    return jsonify([r["categorie"] for r in rows])

@app.route("/api/ajouter", methods=["POST"])
@connexion_requise
def ajouter():
    data = corps_json()
    type_tr = texte(data, "type", 20)
    if type_tr not in ("revenu", "depense", "facture"):
        raise DonneesInvalides("Type de transaction invalide.")
    conn = get_db()
    categorie = normaliser_categorie(conn, session["user_id"], texte(data, "categorie", 100))
    conn.execute("INSERT INTO transactions (user_id,type,categorie,montant,description) VALUES (?,?,?,?,?)",
        (session["user_id"], type_tr, categorie,
         entier(data, "montant"), texte(data, "description", 300)))
    conn.commit(); conn.close()
    return jsonify({"succes":True})

@app.route("/api/modifier/<int:id>", methods=["PUT"])
@connexion_requise
def modifier(id):
    data = corps_json()
    type_tr = texte(data, "type", 20)
    if type_tr not in ("revenu", "depense", "facture"):
        raise DonneesInvalides("Type de transaction invalide.")
    conn = get_db()
    categorie = normaliser_categorie(conn, session["user_id"], texte(data, "categorie", 100))
    conn.execute("UPDATE transactions SET type=?,categorie=?,montant=?,description=? WHERE id=? AND user_id=?",
        (type_tr, categorie, entier(data, "montant"),
         texte(data, "description", 300), id, session["user_id"]))
    conn.commit(); conn.close()
    return jsonify({"succes":True})

@app.route("/api/supprimer/<int:id>", methods=["DELETE"])
@connexion_requise
def supprimer(id):
    conn = get_db()
    conn.execute("DELETE FROM transactions WHERE id=? AND user_id=?", (id,session["user_id"]))
    conn.commit(); conn.close()
    return jsonify({"succes":True})

@app.route("/api/employes")
@connexion_requise
def liste_employes():
    conn = get_db()
    rows = conn.execute("SELECT * FROM employes WHERE user_id=? ORDER BY nom", (session["user_id"],)).fetchall()
    conn.close()
    return jsonify([{"id":r["id"],"nom":r["nom"],"poste":r["poste"],"departement":r["departement"],
        "salaire_base":r["salaire_base"],"email":r["email"],"telephone":r["telephone"],
        "date_embauche":r["date_embauche"],"actif":r["actif"]} for r in rows])

@app.route("/api/employes/ajouter", methods=["POST"])
@connexion_requise
def ajouter_employe():
    data = corps_json()
    conn = get_db()
    conn.execute("INSERT INTO employes (user_id,nom,poste,departement,salaire_base,email,telephone) VALUES (?,?,?,?,?,?,?)",
        (session["user_id"], texte(data, "nom", 100), texte(data, "poste", 100),
         texte(data, "departement", 100), entier(data, "salaire_base"),
         texte(data, "email", 200, obligatoire=False), texte(data, "telephone", 40, obligatoire=False)))
    conn.commit(); conn.close()
    return jsonify({"succes":True})

@app.route("/api/employes/modifier/<int:id>", methods=["PUT"])
@connexion_requise
def modifier_employe(id):
    data = corps_json()
    conn = get_db()
    conn.execute("UPDATE employes SET nom=?,poste=?,departement=?,salaire_base=?,email=?,telephone=? WHERE id=? AND user_id=?",
        (texte(data, "nom", 100), texte(data, "poste", 100), texte(data, "departement", 100),
         entier(data, "salaire_base"), texte(data, "email", 200, obligatoire=False),
         texte(data, "telephone", 40, obligatoire=False), id, session["user_id"]))
    conn.commit(); conn.close()
    return jsonify({"succes":True})

@app.route("/api/employes/supprimer/<int:id>", methods=["DELETE"])
@connexion_requise
def supprimer_employe(id):
    conn = get_db()
    conn.execute("UPDATE employes SET actif=0 WHERE id=? AND user_id=?", (id, session["user_id"]))
    conn.commit(); conn.close()
    return jsonify({"succes":True})

@app.route("/api/salaires")
@connexion_requise
def liste_salaires():
    mois = texte(request.args, "mois", 7, obligatoire=False)
    conn = get_db()
    query = ("SELECT s.*, e.nom as employe_nom, e.poste as employe_poste "
             "FROM salaires s JOIN employes e ON s.employe_id=e.id WHERE s.user_id=?")
    params = [session["user_id"]]
    if mois: query += " AND s.mois=?"; params.append(mois_valide(mois))
    query += " ORDER BY s.id DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return jsonify([{"id":r["id"],"employe_id":r["employe_id"],"employe_nom":r["employe_nom"],
        "employe_poste":r["employe_poste"],"mois":r["mois"],"montant":r["montant"],
        "bonus":r["bonus"],"deductions":r["deductions"],"net_paye":r["net_paye"],
        "statut":r["statut"],"date_paiement":r["date_paiement"]} for r in rows])

@app.route("/api/salaires/generer", methods=["POST"])
@connexion_requise
def generer_salaires():
    data = corps_json()
    mois = mois_valide(texte(data, "mois", 7))
    uid = session["user_id"]
    conn = get_db()
    # Les employes deja fiches ce mois-la sont ignores : on peut donc completer
    # un mois apres l'arrivee d'un nouvel employe, sans doublon ni perte.
    employes = conn.execute(
        "SELECT * FROM employes WHERE actif=1 AND user_id=? AND id NOT IN "
        "(SELECT employe_id FROM salaires WHERE mois=? AND user_id=?)",
        (uid, mois, uid)).fetchall()
    if not employes:
        deja = conn.execute("SELECT COUNT(*) FROM salaires WHERE mois=? AND user_id=?",
                            (mois, uid)).fetchone()[0]
        conn.close()
        if deja:
            return jsonify({"succes": False,
                            "erreur": "Tous les employes actifs ont deja une fiche pour ce mois"})
        return jsonify({"succes": False, "erreur": "Aucun employe actif a traiter"})
    for e in employes:
        conn.execute("INSERT INTO salaires (user_id,employe_id,mois,montant,bonus,deductions,net_paye) VALUES (?,?,?,?,0,0,?)",
            (uid, e["id"], mois, e["salaire_base"], e["salaire_base"]))
    conn.commit(); conn.close()
    return jsonify({"succes": True, "nb": len(employes)})

@app.route("/api/salaires/payer/<int:id>", methods=["PUT"])
@connexion_requise
def payer_salaire(id):
    conn = get_db()
    conn.execute("UPDATE salaires SET statut='paye', date_paiement=to_char(CURRENT_DATE, 'YYYY-MM-DD') WHERE id=? AND user_id=?",
                 (id, session["user_id"]))
    conn.commit(); conn.close()
    return jsonify({"succes": True})

@app.route("/api/salaires/payer-tous", methods=["PUT"])
@connexion_requise
def payer_tous_salaires():
    data = corps_json()
    mois = mois_valide(texte(data, "mois", 7))
    conn = get_db()
    conn.execute("UPDATE salaires SET statut='paye', date_paiement=to_char(CURRENT_DATE, 'YYYY-MM-DD') WHERE mois=? AND statut='en_attente' AND user_id=?",
                 (mois, session["user_id"]))
    conn.commit(); conn.close()
    return jsonify({"succes": True})

@app.route("/api/salaires/modifier/<int:id>", methods=["PUT"])
@connexion_requise
def modifier_salaire(id):
    """Saisie du bonus et des deductions : le net a payer en decoule."""
    data = corps_json()
    bonus = entier(data, "bonus", mini=0)
    deductions = entier(data, "deductions", mini=0)
    conn = get_db()
    sal = conn.execute("SELECT montant FROM salaires WHERE id=? AND user_id=?",
                       (id, session["user_id"])).fetchone()
    if not sal:
        conn.close()
        return jsonify({"succes": False, "erreur": "Fiche introuvable"}), 404
    net = sal["montant"] + bonus - deductions
    if net < 0:
        conn.close()
        raise DonneesInvalides("Les deductions depassent le salaire et le bonus.")
    conn.execute("UPDATE salaires SET bonus=?, deductions=?, net_paye=? WHERE id=? AND user_id=?",
                 (bonus, deductions, net, id, session["user_id"]))
    conn.commit(); conn.close()
    return jsonify({"succes": True, "net_paye": net})

@app.route("/api/budgets")
@connexion_requise
def liste_budgets():
    """Budgets du mois en cours, avec la part deja consommee."""
    uid = session["user_id"]
    mois = texte(request.args, "mois", 7, obligatoire=False) or date.today().strftime("%Y-%m")
    mois_valide(mois)
    conn = get_db()
    rows = conn.execute("SELECT * FROM budgets WHERE user_id=? ORDER BY categorie", (uid,)).fetchall()
    resultat = []
    for b in rows:
        depense = conn.execute(
            "SELECT COALESCE(SUM(montant),0) FROM transactions WHERE user_id=? AND type='depense' "
            "AND LOWER(categorie)=LOWER(?) AND substr(date_ajout,1,7)=?",
            (uid, b["categorie"], mois)).fetchone()[0]
        plafond = b["montant_mensuel"]
        resultat.append({
            "id": b["id"], "categorie": b["categorie"], "montant_mensuel": plafond,
            "depense": depense, "restant": plafond - depense,
            "pourcentage": round(depense * 100.0 / plafond, 1) if plafond else 0,
            "depasse": depense > plafond,
        })
    devise = devise_utilisateur(conn, uid)
    conn.close()
    return jsonify({"mois": mois, "devise": devise, "budgets": resultat,
                    "total_plafond": sum(b["montant_mensuel"] for b in resultat),
                    "total_depense": sum(b["depense"] for b in resultat)})

@app.route("/api/budgets/enregistrer", methods=["POST"])
@connexion_requise
def enregistrer_budget():
    """Cree le budget d'une categorie, ou met a jour son plafond."""
    data = corps_json()
    uid = session["user_id"]
    montant = entier(data, "montant_mensuel", mini=1)
    conn = get_db()
    categorie = normaliser_categorie(conn, uid, texte(data, "categorie", 100))
    existant = conn.execute(
        "SELECT id FROM budgets WHERE user_id=? AND LOWER(categorie)=LOWER(?)",
        (uid, categorie)).fetchone()
    if existant:
        conn.execute("UPDATE budgets SET montant_mensuel=? WHERE id=? AND user_id=?",
                     (montant, existant["id"], uid))
    else:
        conn.execute("INSERT INTO budgets (user_id, categorie, montant_mensuel) VALUES (?,?,?)",
                     (uid, categorie, montant))
    conn.commit(); conn.close()
    return jsonify({"succes": True})

@app.route("/api/budgets/supprimer/<int:id>", methods=["DELETE"])
@connexion_requise
def supprimer_budget(id):
    conn = get_db()
    conn.execute("DELETE FROM budgets WHERE id=? AND user_id=?", (id, session["user_id"]))
    conn.commit(); conn.close()
    return jsonify({"succes": True})

@app.route("/api/recurrences")
@connexion_requise
def liste_recurrences():
    conn = get_db()
    rows = conn.execute("SELECT * FROM recurrences WHERE user_id=? ORDER BY jour_mois, id",
                        (session["user_id"],)).fetchall()
    conn.close()
    return jsonify([{"id":r["id"],"type":r["type"],"categorie":r["categorie"],
                     "montant":r["montant"],"description":r["description"],
                     "jour_mois":r["jour_mois"],"actif":r["actif"],
                     "dernier_genere":r["dernier_genere"]} for r in rows])

@app.route("/api/recurrences/ajouter", methods=["POST"])
@connexion_requise
def ajouter_recurrence():
    data = corps_json()
    uid = session["user_id"]
    type_tr = texte(data, "type", 20)
    if type_tr not in ("revenu", "depense", "facture"):
        raise DonneesInvalides("Type de transaction invalide.")
    jour = entier(data, "jour_mois", mini=1, maxi=28)
    conn = get_db()
    categorie = normaliser_categorie(conn, uid, texte(data, "categorie", 100))
    # Marque le mois precedent comme deja traite : la premiere echeance generee
    # sera celle du mois en cours, sans rattrapage retroactif inattendu.
    conn.execute(
        "INSERT INTO recurrences (user_id,type,categorie,montant,description,jour_mois,dernier_genere) "
        "VALUES (?,?,?,?,?,?,?)",
        (uid, type_tr, categorie, entier(data, "montant", mini=1),
         texte(data, "description", 300), jour, mois_precedent(date.today())))
    conn.commit(); conn.close()
    return jsonify({"succes": True})

@app.route("/api/recurrences/basculer/<int:id>", methods=["PUT"])
@connexion_requise
def basculer_recurrence(id):
    """Active ou met en pause une echeance recurrente."""
    conn = get_db()
    ligne = conn.execute("SELECT actif FROM recurrences WHERE id=? AND user_id=?",
                         (id, session["user_id"])).fetchone()
    if not ligne:
        conn.close()
        return jsonify({"succes": False, "erreur": "Echeance introuvable"}), 404
    nouvel_etat = 0 if ligne["actif"] else 1
    conn.execute("UPDATE recurrences SET actif=? WHERE id=? AND user_id=?",
                 (nouvel_etat, id, session["user_id"]))
    conn.commit(); conn.close()
    return jsonify({"succes": True, "actif": nouvel_etat})

@app.route("/api/recurrences/supprimer/<int:id>", methods=["DELETE"])
@connexion_requise
def supprimer_recurrence(id):
    conn = get_db()
    conn.execute("DELETE FROM recurrences WHERE id=? AND user_id=?", (id, session["user_id"]))
    conn.commit(); conn.close()
    return jsonify({"succes": True})

@app.route("/admin")
def page_admin():
    if "user_id" not in session:
        return redirect("/login")
    conn = get_db()
    autorise = est_admin(conn, session["user_id"])
    conn.close()
    if not autorise:
        return redirect("/dashboard")
    return render_template("admin.html", user_nom=session["user_nom"])

@app.route("/api/admin/statistiques")
@admin_requis
def admin_statistiques():
    conn = get_db()
    lire = lambda requete: conn.execute(requete).fetchone()[0]
    stats = {
        "comptes": lire("SELECT COUNT(*) FROM users"),
        "comptes_actifs": lire("SELECT COUNT(*) FROM users WHERE actif=1"),
        "comptes_suspendus": lire("SELECT COUNT(*) FROM users WHERE actif=0"),
        "administrateurs": lire("SELECT COUNT(*) FROM users WHERE role='admin'"),
        "mode_entreprise": lire("SELECT COUNT(*) FROM users WHERE mode='entreprise'"),
        "mode_perso": lire("SELECT COUNT(*) FROM users WHERE mode='perso'"),
        "transactions": lire("SELECT COUNT(*) FROM transactions"),
        "budgets": lire("SELECT COUNT(*) FROM budgets"),
        "recurrences": lire("SELECT COUNT(*) FROM recurrences"),
        "employes": lire("SELECT COUNT(*) FROM employes WHERE actif=1"),
        "fiches_paie": lire("SELECT COUNT(*) FROM salaires"),
        "echecs_connexion": lire(
            "SELECT COUNT(*) FROM tentatives_connexion WHERE moment > now() - interval '24 hours'"),
    }
    inscriptions = conn.execute(
        "SELECT date_creation as jour, COUNT(*) as nb FROM users "
        "GROUP BY date_creation ORDER BY jour DESC LIMIT 30").fetchall()
    conn.close()
    stats["inscriptions"] = [{"jour": r["jour"], "nb": r["nb"]} for r in reversed(inscriptions)]
    return jsonify(stats)

@app.route("/api/admin/comptes")
@admin_requis
def admin_comptes():
    """Liste des comptes avec des volumes, jamais le detail des montants."""
    recherche = texte(request.args, "q", 100, obligatoire=False)
    conn = get_db()
    requete = (
        "SELECT u.id, u.nom, u.email, u.mode, u.role, u.actif, u.date_creation, "
        "u.nom_entreprise, "
        "(SELECT COUNT(*) FROM transactions t WHERE t.user_id=u.id) as nb_transactions, "
        "(SELECT COUNT(*) FROM employes e WHERE e.user_id=u.id AND e.actif=1) as nb_employes "
        "FROM users u")
    params = []
    if recherche:
        requete += " WHERE u.nom ILIKE ? OR u.email ILIKE ?"
        motif = "%" + recherche + "%"
        params += [motif, motif]
    requete += " ORDER BY u.id"
    rows = conn.execute(requete, params).fetchall()
    conn.close()
    return jsonify([{
        "id": r["id"], "nom": r["nom"], "email": r["email"], "mode": r["mode"],
        "role": r["role"], "actif": r["actif"], "date_creation": r["date_creation"],
        "nom_entreprise": r["nom_entreprise"] or "",
        "nb_transactions": r["nb_transactions"], "nb_employes": r["nb_employes"],
        "moi": r["id"] == session["user_id"],
    } for r in rows])

@app.route("/api/admin/comptes/<int:id>/suspendre", methods=["PUT"])
@admin_requis
def admin_suspendre(id):
    if id == session["user_id"]:
        return jsonify({"succes": False,
                        "erreur": "Vous ne pouvez pas suspendre votre propre compte"}), 400
    conn = get_db()
    cible = conn.execute("SELECT email, actif, role FROM users WHERE id=?", (id,)).fetchone()
    if not cible:
        conn.close()
        return jsonify({"succes": False, "erreur": "Compte introuvable"}), 404
    nouvel_etat = 0 if cible["actif"] else 1
    # Ne jamais suspendre le dernier administrateur actif.
    if nouvel_etat == 0 and cible["role"] == "admin":
        restants = conn.execute(
            "SELECT COUNT(*) FROM users WHERE role='admin' AND actif=1 AND id<>?", (id,)).fetchone()[0]
        if restants == 0:
            conn.close()
            return jsonify({"succes": False,
                            "erreur": "Impossible : ce serait le dernier administrateur actif"}), 400
    conn.execute("UPDATE users SET actif=? WHERE id=?", (nouvel_etat, id))
    journaliser(conn, "suspension" if nouvel_etat == 0 else "reactivation", cible["email"])
    conn.commit()
    conn.close()
    return jsonify({"succes": True, "actif": nouvel_etat})

@app.route("/api/admin/comptes/<int:id>/role", methods=["PUT"])
@admin_requis
def admin_role(id):
    data = corps_json()
    role = texte(data, "role", 20)
    if role not in ("admin", "comptable"):
        raise DonneesInvalides("Role inconnu.")
    conn = get_db()
    cible = conn.execute("SELECT email, role FROM users WHERE id=?", (id,)).fetchone()
    if not cible:
        conn.close()
        return jsonify({"succes": False, "erreur": "Compte introuvable"}), 404
    if role != "admin" and cible["role"] == "admin":
        restants = conn.execute(
            "SELECT COUNT(*) FROM users WHERE role='admin' AND actif=1 AND id<>?", (id,)).fetchone()[0]
        if restants == 0:
            conn.close()
            return jsonify({"succes": False,
                            "erreur": "Impossible : ce serait le dernier administrateur"}), 400
    conn.execute("UPDATE users SET role=? WHERE id=?", (role, id))
    journaliser(conn, "changement de role", cible["email"], "vers " + role)
    conn.commit()
    conn.close()
    if id == session["user_id"]:
        session["user_role"] = role
    return jsonify({"succes": True, "role": role})

@app.route("/api/admin/comptes/<int:id>", methods=["DELETE"])
@admin_requis
def admin_supprimer_compte(id):
    if id == session["user_id"]:
        return jsonify({"succes": False,
                        "erreur": "Utilisez les parametres pour supprimer votre propre compte"}), 400
    conn = get_db()
    cible = conn.execute("SELECT email, role FROM users WHERE id=?", (id,)).fetchone()
    if not cible:
        conn.close()
        return jsonify({"succes": False, "erreur": "Compte introuvable"}), 404
    if cible["role"] == "admin":
        restants = conn.execute(
            "SELECT COUNT(*) FROM users WHERE role='admin' AND actif=1 AND id<>?", (id,)).fetchone()[0]
        if restants == 0:
            conn.close()
            return jsonify({"succes": False,
                            "erreur": "Impossible : ce serait le dernier administrateur"}), 400
    # L'ordre respecte les cles etrangeres.
    for table in ("salaires", "employes", "budgets", "recurrences", "transactions"):
        conn.execute("DELETE FROM %s WHERE user_id=?" % table, (id,))
    conn.execute("DELETE FROM users WHERE id=?", (id,))
    journaliser(conn, "suppression de compte", cible["email"])
    conn.commit()
    conn.close()
    return jsonify({"succes": True})

@app.route("/api/admin/securite")
@admin_requis
def admin_securite():
    """Echecs de connexion recents, pour reperer un compte bloque ou attaque."""
    conn = get_db()
    rows = conn.execute(
        "SELECT email, COUNT(*) as essais, MAX(moment) as dernier "
        "FROM tentatives_connexion WHERE moment > now() - interval '%d minutes' "
        "GROUP BY email ORDER BY essais DESC LIMIT 50" % FENETRE_TENTATIVES).fetchall()
    conn.close()
    return jsonify([{
        "email": r["email"], "essais": r["essais"],
        "dernier": r["dernier"].strftime("%Y-%m-%d %H:%M") if r["dernier"] else "",
        "bloque": r["essais"] >= LIMITE_TENTATIVES,
    } for r in rows])

@app.route("/api/admin/debloquer", methods=["POST"])
@admin_requis
def admin_debloquer():
    data = corps_json()
    email = texte(data, "email", 200).lower()
    conn = get_db()
    conn.execute("DELETE FROM tentatives_connexion WHERE email=?", (email,))
    journaliser(conn, "deblocage", email)
    conn.commit()
    conn.close()
    return jsonify({"succes": True})

@app.route("/api/admin/journal")
@admin_requis
def admin_journal():
    conn = get_db()
    rows = conn.execute(
        "SELECT admin_email, action, cible, detail, moment FROM journal_admin "
        "ORDER BY id DESC LIMIT 100").fetchall()
    conn.close()
    return jsonify([{
        "admin": r["admin_email"], "action": r["action"], "cible": r["cible"],
        "detail": r["detail"],
        "moment": r["moment"].strftime("%Y-%m-%d %H:%M") if r["moment"] else "",
    } for r in rows])

@app.route("/api/salaires/pdf/<int:id>")
def pdf_salaire(id):
    if "user_id" not in session:
        return redirect("/login")
    conn = get_db()
    sal = conn.execute("""SELECT s.*, e.nom as employe_nom, e.poste as employe_poste,
        e.departement as employe_dept, e.email as employe_email
        FROM salaires s JOIN employes e ON s.employe_id=e.id
        WHERE s.id=? AND s.user_id=?""", (id, session["user_id"])).fetchone()
    devise = devise_utilisateur(conn, session["user_id"])
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
    titre_style = ParagraphStyle('titre', parent=styles['Title'], fontSize=24, textColor=colors.HexColor('#3b82f6'), spaceAfter=10)
    elements.append(Paragraph("BudgetLab", titre_style))
    elements.append(Paragraph("Fiche de paie", styles['Title']))
    elements.append(Spacer(1, 20))
    info_style = ParagraphStyle('info', parent=styles['Normal'], fontSize=12, spaceAfter=5)
    elements.append(Paragraph("<b>Employe :</b> " + sal["employe_nom"], info_style))
    elements.append(Paragraph("<b>Poste :</b> " + sal["employe_poste"], info_style))
    elements.append(Paragraph("<b>Departement :</b> " + sal["employe_dept"], info_style))
    elements.append(Paragraph("<b>Email :</b> " + (sal["employe_email"] or ""), info_style))
    elements.append(Paragraph("<b>Periode :</b> " + sal["mois"], info_style))
    elements.append(Spacer(1, 20))
    data_table = [["Description", "Montant (%s)" % devise],
        ["Salaire de base", "{:,}".format(sal["montant"]).replace(",", " ")],
        ["Bonus", "{:,}".format(sal["bonus"]).replace(",", " ")],
        ["Deductions", "-{:,}".format(sal["deductions"]).replace(",", " ")],
        ["", ""],
        ["NET A PAYER", "{:,}".format(sal["net_paye"]).replace(",", " ")]]
    table = Table(data_table, colWidths=[10*cm, 6*cm])
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
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10)]))
    elements.append(table)
    elements.append(Spacer(1, 30))
    statut_text = "PAYE" if sal["statut"] == "paye" else "EN ATTENTE"
    statut_color = '#10b981' if sal["statut"] == "paye" else '#f59e0b'
    statut_style = ParagraphStyle('statut', parent=styles['Normal'], fontSize=14, textColor=colors.HexColor(statut_color))
    elements.append(Paragraph("<b>Statut : " + statut_text + "</b>", statut_style))
    if sal["date_paiement"]:
        elements.append(Paragraph("Date de paiement : " + sal["date_paiement"], info_style))
    elements.append(Spacer(1, 40))
    elements.append(Paragraph("Document genere par BudgetLab", ParagraphStyle('footer', parent=styles['Normal'], fontSize=9, textColor=colors.grey)))
    doc.build(elements)
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name="fiche_paie_" + sal["employe_nom"].replace(" ", "_") + "_" + sal["mois"] + ".pdf", mimetype='application/pdf')

if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=5000)
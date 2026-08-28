"""Couche d'acces Postgres pour BudgetLab.

Vercel est serverless : le disque est en lecture seule et ephemere, donc
SQLite ne peut pas y stocker les donnees. Les tables vivent maintenant dans
Postgres (Neon), accessible via la variable d'environnement DATABASE_URL.

Ce module garde volontairement l'API utilisee partout dans app.py
(conn.execute(...).fetchone(), acces par nom ou par position) pour que le
reste du code reste identique.
"""
import os
import psycopg

IntegrityError = psycopg.IntegrityError


def _charger_env_local():
    """Lit un fichier .env a la racine (developpement local uniquement).

    Sur Vercel les variables viennent de l'environnement, ce fichier n'existe pas.
    """
    chemin = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.exists(chemin):
        return
    with open(chemin, encoding="utf-8") as f:
        for ligne in f:
            ligne = ligne.strip()
            if not ligne or ligne.startswith("#") or "=" not in ligne:
                continue
            cle, valeur = ligne.split("=", 1)
            os.environ.setdefault(cle.strip(), valeur.strip().strip('"').strip("'"))


_charger_env_local()


class Row(dict):
    """Ligne accessible par nom (r["nom"]) ou par position (r[0])."""

    def __getitem__(self, cle):
        if isinstance(cle, int):
            return list(self.values())[cle]
        return dict.__getitem__(self, cle)


def _row_factory(curseur):
    colonnes = [c.name for c in curseur.description] if curseur.description else []

    def construire(valeurs):
        return Row(zip(colonnes, valeurs))

    return construire


class Connexion:
    """Traduit les placeholders ? de SQLite vers les %s de Postgres."""

    def __init__(self, brute):
        self._brute = brute

    def execute(self, requete, params=()):
        return self._brute.execute(requete.replace("?", "%s"), tuple(params) or None)

    def commit(self):
        self._brute.commit()

    def rollback(self):
        self._brute.rollback()

    def close(self):
        self._brute.close()


def url_base():
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        raise RuntimeError(
            "DATABASE_URL n'est pas definie. En local, cree un fichier .env ; "
            "sur Vercel, ajoute la variable dans Settings > Environment Variables."
        )
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    return url


def get_db():
    return Connexion(psycopg.connect(url_base(), row_factory=_row_factory))


def init_db():
    """Cree les tables si elles n'existent pas. A lancer une fois : python -m scripts.init_db"""
    conn = get_db()
    conn.execute("""CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        nom TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        mot_de_passe TEXT NOT NULL,
        role TEXT DEFAULT 'comptable',
        mode TEXT DEFAULT 'perso',
        nom_entreprise TEXT DEFAULT ''
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS employes (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id),
        nom TEXT NOT NULL,
        poste TEXT NOT NULL,
        departement TEXT NOT NULL,
        salaire_base INTEGER NOT NULL,
        email TEXT,
        telephone TEXT,
        date_embauche TEXT DEFAULT to_char(CURRENT_DATE, 'YYYY-MM-DD'),
        actif INTEGER DEFAULT 1
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS transactions (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id),
        type TEXT NOT NULL,
        categorie TEXT NOT NULL,
        montant INTEGER NOT NULL,
        description TEXT NOT NULL,
        date_ajout TEXT DEFAULT to_char(CURRENT_DATE, 'YYYY-MM-DD')
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS salaires (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id),
        employe_id INTEGER NOT NULL REFERENCES employes(id),
        mois TEXT NOT NULL,
        montant INTEGER NOT NULL,
        bonus INTEGER DEFAULT 0,
        deductions INTEGER DEFAULT 0,
        net_paye INTEGER NOT NULL,
        statut TEXT DEFAULT 'en_attente',
        date_paiement TEXT
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS budgets (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id),
        categorie TEXT NOT NULL,
        montant_mensuel INTEGER NOT NULL
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS recurrences (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id),
        type TEXT NOT NULL,
        categorie TEXT NOT NULL,
        montant INTEGER NOT NULL,
        description TEXT NOT NULL,
        jour_mois INTEGER NOT NULL DEFAULT 1,
        actif INTEGER DEFAULT 1,
        dernier_genere TEXT DEFAULT ''
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS journal_admin (
        id SERIAL PRIMARY KEY,
        admin_id INTEGER NOT NULL REFERENCES users(id),
        admin_email TEXT NOT NULL,
        action TEXT NOT NULL,
        cible TEXT NOT NULL DEFAULT '',
        detail TEXT NOT NULL DEFAULT '',
        moment TIMESTAMPTZ NOT NULL DEFAULT now()
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS tentatives_connexion (
        id SERIAL PRIMARY KEY,
        email TEXT NOT NULL,
        ip TEXT NOT NULL,
        moment TIMESTAMPTZ NOT NULL DEFAULT now()
    )""")
    # Empeche deux comptes ne differant que par la casse de l'email.
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email_lower ON users (LOWER(email))")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tentatives_moment ON tentatives_connexion (moment)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_employes_user ON employes (user_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_salaires_user ON salaires (user_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_transactions_user ON transactions (user_id)")
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_budgets_user_categorie "
                 "ON budgets (user_id, LOWER(categorie))")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_recurrences_user ON recurrences (user_id)")
    # Colonne ajoutee apres la mise en service : la devise etait codee en dur.
    conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS devise TEXT DEFAULT 'FCFA'")
    # Un compte suspendu conserve ses donnees mais ne peut plus se connecter.
    conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS actif INTEGER DEFAULT 1")
    conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS date_creation TEXT "
                 "DEFAULT to_char(CURRENT_DATE, 'YYYY-MM-DD')")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_journal_moment ON journal_admin (moment)")
    conn.commit()
    conn.close()

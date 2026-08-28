"""Copie les donnees de finances.db (SQLite) vers la base Postgres DATABASE_URL.

A lancer une seule fois, apres scripts/init_db.py :
    python scripts/migrer_sqlite_vers_postgres.py

Les identifiants sont conserves, et les sequences Postgres sont resynchronisees
pour que les prochains INSERT ne rentrent pas en collision.
"""
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import get_db  # noqa: E402

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHEMIN_SQLITE = os.path.join(RACINE, "finances.db")

# Ordre important : les cles etrangeres imposent users et employes en premier.
TABLES = {
    "users": ["id", "nom", "email", "mot_de_passe", "role", "mode", "nom_entreprise"],
    "employes": ["id", "nom", "poste", "departement", "salaire_base", "email",
                 "telephone", "date_embauche", "actif"],
    "transactions": ["id", "user_id", "type", "categorie", "montant", "description",
                     "date_ajout"],
    "salaires": ["id", "employe_id", "mois", "montant", "bonus", "deductions",
                 "net_paye", "statut", "date_paiement"],
}

# Dans l'ancienne base, employes et salaires n'appartenaient a personne : ils
# etaient visibles par tous les comptes. La migration les rattache donc a un
# proprietaire unique, faute de quoi ils resteraient partages.
TABLES_A_RATTACHER = ("employes", "salaires")


def colonnes_existantes(src, table):
    return {ligne[1] for ligne in src.execute("PRAGMA table_info(%s)" % table)}


def main():
    if not os.path.exists(CHEMIN_SQLITE):
        print("Aucun finances.db trouve : rien a migrer.")
        return

    src = sqlite3.connect(CHEMIN_SQLITE)
    src.row_factory = sqlite3.Row
    dest = get_db()

    proprietaire = dest.execute("SELECT MIN(id) FROM users").fetchone()[0]

    for table, colonnes in TABLES.items():
        dispo = colonnes_existantes(src, table)
        if not dispo:
            print("%-13s table absente de SQLite, ignoree" % table)
            continue
        colonnes = [c for c in colonnes if c in dispo]

        deja = dest.execute("SELECT COUNT(*) FROM " + table).fetchone()[0]
        if deja:
            print("%-13s %d ligne(s) deja presente(s) en Postgres, ignoree" % (table, deja))
            continue

        lignes = src.execute("SELECT %s FROM %s" % (", ".join(colonnes), table)).fetchall()

        rattacher = table in TABLES_A_RATTACHER and "user_id" not in colonnes
        if rattacher and lignes and proprietaire is None:
            print("%-13s %d ligne(s) ignoree(s) : aucun compte utilisateur en base "
                  "pour les rattacher" % (table, len(lignes)))
            continue

        colonnes_cibles = (["user_id"] + colonnes) if rattacher else colonnes
        marques = ", ".join(["?"] * len(colonnes_cibles))
        for ligne in lignes:
            valeurs = tuple(ligne[c] for c in colonnes)
            if rattacher:
                valeurs = (proprietaire,) + valeurs
            dest.execute(
                "INSERT INTO %s (%s) VALUES (%s)"
                % (table, ", ".join(colonnes_cibles), marques),
                valeurs,
            )
        # La sequence SERIAL ignore les id inseres explicitement : on la recale.
        dest.execute(
            "SELECT setval(pg_get_serial_sequence('%s', 'id'), "
            "COALESCE((SELECT MAX(id) FROM %s), 1))" % (table, table)
        ).fetchone()
        print("%-13s %d ligne(s) copiee(s)" % (table, len(lignes)))

    dest.commit()
    dest.close()
    src.close()
    print("Migration terminee.")
    if proprietaire is not None:
        print("Employes et salaires rattaches au compte utilisateur id=%d." % proprietaire)
    print("Les mots de passe existants seront reconvertis en scrypt a la "
          "prochaine connexion de chaque utilisateur.")


if __name__ == "__main__":
    main()

"""Donne (ou retire) les droits d'administrateur a un compte existant.

C'est le seul moyen de creer le premier administrateur : aucune page de
l'application ne permet de s'attribuer ce role soi-meme.

Usage :
    python scripts/promouvoir_admin.py vous@exemple.com
    python scripts/promouvoir_admin.py vous@exemple.com --retirer
    python scripts/promouvoir_admin.py --lister
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import get_db  # noqa: E402


def lister(conn):
    admins = conn.execute(
        "SELECT id, nom, email, actif FROM users WHERE role='admin' ORDER BY id").fetchall()
    if not admins:
        print("Aucun administrateur pour le moment.")
        return
    print("Administrateurs :")
    for a in admins:
        etat = "actif" if a["actif"] else "suspendu"
        print("  #%-4s %-28s %-34s %s" % (a["id"], a["nom"], a["email"], etat))


def main():
    arguments = [a for a in sys.argv[1:]]
    retirer = "--retirer" in arguments
    arguments = [a for a in arguments if not a.startswith("--")]

    conn = get_db()

    if "--lister" in sys.argv[1:]:
        lister(conn)
        conn.close()
        return

    if not arguments:
        print(__doc__)
        lister(conn)
        conn.close()
        sys.exit(1)

    email = arguments[0].strip().lower()
    user = conn.execute(
        "SELECT id, nom, email, role FROM users WHERE LOWER(email)=?", (email,)).fetchone()
    if not user:
        print("Aucun compte avec l'adresse %s." % email)
        print("Creez d'abord le compte depuis la page d'inscription, puis relancez ce script.")
        conn.close()
        sys.exit(1)

    if retirer:
        restants = conn.execute(
            "SELECT COUNT(*) FROM users WHERE role='admin' AND actif=1 AND id<>?",
            (user["id"],)).fetchone()[0]
        if user["role"] == "admin" and restants == 0:
            print("Refus : %s est le dernier administrateur actif." % email)
            conn.close()
            sys.exit(1)
        conn.execute("UPDATE users SET role='comptable' WHERE id=?", (user["id"],))
        conn.commit()
        print("Droits d'administrateur retires a %s (%s)." % (user["nom"], user["email"]))
    else:
        conn.execute("UPDATE users SET role='admin' WHERE id=?", (user["id"],))
        conn.commit()
        print("%s (%s) est desormais administrateur." % (user["nom"], user["email"]))
        print("L'espace d'administration est accessible sur /admin.")

    print()
    lister(conn)
    conn.close()


if __name__ == "__main__":
    main()

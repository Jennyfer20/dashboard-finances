# BudgetLab

Application web de gestion de finances personnelles et de paie.

## Technologies utilisees

- Python (Flask)
- HTML / CSS / JavaScript
- PostgreSQL (base de donnees, hebergee sur Neon)
- Chart.js (graphiques)
- ReportLab (fiches de paie en PDF)

## Fonctionnalites

### Finances
- Tableau de bord avec solde, revenus, depenses et benefice
- Graphique des depenses par categorie et evolution mensuelle
- Ajouter, modifier et supprimer des transactions
- **Budgets mensuels par categorie**, avec barre de progression et alerte de depassement
- **Echeances recurrentes** : loyer, abonnements... crees automatiquement chaque mois
- **Recherche** dans les descriptions et categories, avec pagination
- **Export CSV** de toutes les transactions, ouvrable directement dans Excel
- **Devise configurable** (FCFA, EUR, USD, GBP, CAD, CHF, MAD, TND, XOF, XAF)
- Les categories sont normalisees : "Loyer" et "loyer" ne font qu'une

### Paie (mode entreprise)
- Gestion des employes par departement
- Generation des salaires du mois, completable apres l'arrivee d'un employe
- **Bonus et deductions** saisissables, net a payer recalcule automatiquement
- Fiches de paie en PDF a la devise du compte

### Interface
- Mode sombre / mode clair
- Application installable (PWA), utilisable sur mobile
- Deux modes : personnel ou entreprise, l'interface s'adapte

## Administration

L'espace d'administration est accessible sur `/admin`, reserve aux comptes ayant
le role `admin`.

### Creer le premier administrateur

Aucune page ne permet de s'attribuer ce role soi-meme. Il faut passer par le
script, apres avoir cree le compte normalement depuis la page d'inscription :

```bash
python scripts/promouvoir_admin.py vous@exemple.com
python scripts/promouvoir_admin.py --lister
python scripts/promouvoir_admin.py vous@exemple.com --retirer
```

Une fois le premier administrateur en place, il peut nommer les suivants depuis
l'interface.

### Ce que l'administrateur peut faire

- Consulter les statistiques globales et la courbe des inscriptions
- Lister et rechercher les comptes, avec des volumes (nombre de transactions,
  d'employes) mais **jamais le detail des montants**
- Suspendre ou reactiver un compte : les donnees sont conservees, mais la
  connexion est refusee
- Nommer ou retrograder un administrateur
- Supprimer definitivement un compte et toutes ses donnees
- Voir les echecs de connexion recents et debloquer une adresse
- Consulter le journal des actions d'administration

### Ce que l'administrateur ne peut pas faire

Par choix de conception, l'administrateur **n'a pas acces au contenu financier**
des comptes : ni les transactions, ni les budgets, ni les fiches de paie. Une
application qui manipule des salaires ne doit pas permettre a un administrateur
de lire les finances de ses utilisateurs.

### Garde-fous

- Le role est relu en base a chaque requete : une session ouverte avant une
  retrogradation perd ses droits immediatement.
- Un administrateur ne peut ni se suspendre, ni se supprimer lui-meme.
- Le dernier administrateur actif ne peut etre ni retrograde, ni suspendu, ni
  supprime : impossible de se verrouiller dehors.
- Chaque suspension, suppression, changement de role et deblocage est
  journalise avec son auteur et son horodatage.

## Fonctionnement des echeances recurrentes

Il n'y a pas de tache planifiee en environnement serverless. Les echeances dues
sont donc creees a la consultation du tableau de bord, avec rattrapage sur les
12 derniers mois au maximum. Une echeance nouvellement creee demarre au mois en
cours : elle ne genere pas d'historique retroactif.

## Configuration

L'application lit deux variables d'environnement :

| Variable       | Role                                                   |
| -------------- | ------------------------------------------------------ |
| `DATABASE_URL` | Chaine de connexion Postgres (Neon)                    |
| `SECRET_KEY`   | Cle de signature des cookies de session                |

Les deux sont **obligatoires** : sans `SECRET_KEY`, l'application refuse de
demarrer, car une cle connue permettrait de forger n'importe quelle session.
La generer avec :

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

En local, copier `.env.example` en `.env` et remplir les valeurs.

## Lancer en local

```bash
python -m venv .venv
.venv\Scripts\activate         # Windows
pip install -r requirements.txt
python scripts/init_db.py      # cree les tables (une seule fois)
python app.py                  # http://localhost:5000
```

## Deploiement sur Vercel

L'application tourne en fonction serverless : `api/index.py` expose l'objet Flask
et `vercel.json` redirige toutes les URL vers cette fonction.

1. Creer une base Postgres sur [Neon](https://neon.com) et copier la connection string.
2. Sur [vercel.com](https://vercel.com) : **Add New > Project**, importer ce depot GitHub.
3. Dans **Settings > Environment Variables**, ajouter `DATABASE_URL` et `SECRET_KEY`.
4. Deployer, puis creer les tables une fois depuis le poste local :
   ```bash
   python scripts/init_db.py
   ```

Le disque etant en lecture seule sur Vercel, aucune donnee n'est stockee dans des
fichiers : tout passe par Postgres.

## Migrer les anciennes donnees SQLite

Si un fichier `finances.db` contient des donnees a conserver :

```bash
python scripts/init_db.py
python scripts/migrer_sqlite_vers_postgres.py
```

## Securite

- Mots de passe haches avec **scrypt** (via Werkzeug). Les comptes crees avant
  la migration utilisaient un SHA-256 non sale : il est accepte une derniere
  fois a la connexion, puis remplace automatiquement.
- **Cloisonnement par compte** : employes, salaires et transactions portent un
  `user_id`, et chaque requete filtre dessus. Un compte ne peut ni lire ni
  modifier les donnees d'un autre, fiches de paie PDF comprises.
- **Limitation du bruteforce** : au-dela de 10 echecs de connexion en 15 minutes
  (par email ou par adresse IP), les tentatives sont refusees en 429.
- **Echappement HTML** cote client (`esc()` dans `static/script.js`) sur toutes
  les donnees saisies, pour empecher l'injection de balises.
- **Cookies de session** en `HttpOnly`, `SameSite=Lax`, et `Secure` en production.
- **Validation des entrees** : toute saisie invalide renvoie une erreur 400
  explicite plutot qu'une erreur 500.
- **En-tetes** : CSP, `X-Frame-Options`, `X-Content-Type-Options`,
  `Referrer-Policy`, et HSTS en production.
- Toutes les requetes SQL sont parametrees : aucune injection possible.

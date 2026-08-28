/* Espace d'administration.
 *
 * Toutes les verifications de droits sont faites cote serveur : ce fichier ne
 * fait qu'afficher ce que l'API accepte de renvoyer.
 */
(function () {
    "use strict";

    function esc(v) {
        if (v === null || v === undefined) return "";
        return String(v).replace(/[&<>"']/g, function (c) {
            return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
        });
    }

    function vide(message) {
        return '<p class="etat-vide">' + esc(message) + "</p>";
    }

    // ------------------------------------------------------- navigation --
    window.changerVue = function (id, lien) {
        document.querySelectorAll(".page").forEach(function (p) { p.style.display = "none"; });
        document.getElementById(id).style.display = "block";
        document.querySelectorAll(".sidebar a").forEach(function (a) { a.classList.remove("active"); });
        if (lien) lien.classList.add("active");
        fermerMenu();
        if (id === "vue-stats") chargerStatistiques();
        if (id === "vue-comptes") chargerComptes();
        if (id === "vue-securite") chargerSecurite();
        if (id === "vue-journal") chargerJournal();
    };

    function fermerMenu() {
        document.getElementById("sidebar").classList.remove("open");
        document.getElementById("sidebar-overlay").classList.remove("active");
    }

    // --------------------------------------------------- vue d'ensemble --
    var LIBELLES = [
        ["comptes", "Comptes", "#2563eb"],
        ["comptes_actifs", "Actifs", "#10b981"],
        ["comptes_suspendus", "Suspendus", "#ef4444"],
        ["administrateurs", "Administrateurs", "#8b5cf6"],
        ["mode_entreprise", "Mode entreprise", "#ec4899"],
        ["mode_perso", "Mode personnel", "#f59e0b"],
        ["transactions", "Transactions", "#2563eb"],
        ["budgets", "Budgets", "#10b981"],
        ["recurrences", "Echeances", "#8b5cf6"],
        ["employes", "Employes", "#ec4899"],
        ["fiches_paie", "Fiches de paie", "#f59e0b"],
        ["echecs_connexion", "Echecs 24 h", "#ef4444"]
    ];

    function chargerStatistiques() {
        fetch("/api/admin/statistiques").then(function (r) { return r.json(); }).then(function (d) {
            var c = document.getElementById("cartes-stats");
            c.innerHTML = LIBELLES.map(function (l) {
                return '<div class="carte" style="border-top-color:' + l[2] + '">'
                    + "<h3>" + esc(l[1]) + "</h3><p>" + Number(d[l[0]] || 0).toLocaleString() + "</p></div>";
            }).join("");

            var g = document.getElementById("graphe-inscriptions");
            var jours = d.inscriptions || [];
            if (!jours.length) { g.innerHTML = vide("Aucune inscription enregistree."); return; }
            var max = Math.max.apply(null, jours.map(function (j) { return j.nb; }));
            g.innerHTML = jours.map(function (j) {
                var hauteur = Math.max(6, Math.round((j.nb / max) * 100));
                return '<span class="barre" title="' + esc(j.jour) + " : " + j.nb + ' compte(s)">'
                    + '<i style="height:' + hauteur + '%"></i></span>';
            }).join("");
        });
    }

    // --------------------------------------------------------- comptes --
    function chargerComptes() {
        var q = document.getElementById("recherche-compte").value.trim();
        fetch("/api/admin/comptes" + (q ? "?q=" + encodeURIComponent(q) : ""))
            .then(function (r) { return r.json(); })
            .then(function (comptes) {
                document.getElementById("total-comptes").textContent =
                    comptes.length ? "(" + comptes.length + ")" : "";
                var c = document.getElementById("liste-comptes");
                if (!comptes.length) { c.innerHTML = vide("Aucun compte ne correspond."); return; }
                c.innerHTML = "";
                comptes.forEach(function (u) {
                    var div = document.createElement("div");
                    div.className = "transaction-item";
                    if (!u.actif) div.style.opacity = ".55";
                    var etiquettes =
                        '<span class="badge ' + (u.role === "admin" ? "badge-blue" : "badge-green") + '">'
                        + (u.role === "admin" ? "admin" : "utilisateur") + "</span>"
                        + ' <span class="badge badge-orange">' + esc(u.mode) + "</span>"
                        + (u.actif ? "" : ' <span class="badge badge-red">suspendu</span>')
                        + (u.moi ? ' <span class="badge badge-blue">vous</span>' : "");

                    div.innerHTML =
                        '<div class="transaction-info">'
                        + '<span class="transaction-desc">' + esc(u.nom)
                        + (u.nom_entreprise ? ' <span style="font-weight:400;color:var(--texte-faible)">- '
                            + esc(u.nom_entreprise) + "</span>" : "") + "</span>"
                        + '<span class="transaction-cat">' + etiquettes + "</span>"
                        + '<span class="transaction-date">' + esc(u.email)
                        + " &middot; inscrit le " + esc(u.date_creation)
                        + " &middot; " + u.nb_transactions + " transaction(s)"
                        + (u.nb_employes ? " &middot; " + u.nb_employes + " employe(s)" : "")
                        + "</span></div>"
                        + '<div class="transaction-actions">'
                        + (u.moi ? '<span style="color:var(--texte-faible);font-size:.8rem">votre compte</span>'
                            : '<button class="btn-modifier act-role" data-id="' + u.id + '" data-role="'
                              + esc(u.role) + '" data-nom="' + esc(u.nom) + '">'
                              + (u.role === "admin" ? "Retirer admin" : "Nommer admin") + "</button>"
                            + '<button class="btn-modifier act-suspendre" data-id="' + u.id
                              + '" data-nom="' + esc(u.nom) + '">'
                              + (u.actif ? "Suspendre" : "Reactiver") + "</button>"
                            + '<button class="btn-supprimer act-supprimer" data-id="' + u.id
                              + '" data-nom="' + esc(u.nom) + '">Supprimer</button>')
                        + "</div>";
                    c.appendChild(div);
                });
                brancherActions();
            });
    }

    function appeler(url, options, succes) {
        fetch(url, options).then(function (r) { return r.json(); }).then(function (d) {
            if (d.succes) { succes(); }
            else { alert(d.erreur || "Action impossible."); }
        });
    }

    function brancherActions() {
        document.querySelectorAll(".act-suspendre").forEach(function (b) {
            b.addEventListener("click", function () {
                appeler("/api/admin/comptes/" + b.dataset.id + "/suspendre", { method: "PUT" },
                        chargerComptes);
            });
        });
        document.querySelectorAll(".act-role").forEach(function (b) {
            b.addEventListener("click", function () {
                var nouveau = b.dataset.role === "admin" ? "comptable" : "admin";
                if (!confirm("Passer " + b.dataset.nom + " en role " + nouveau + " ?")) return;
                appeler("/api/admin/comptes/" + b.dataset.id + "/role", {
                    method: "PUT",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ role: nouveau })
                }, chargerComptes);
            });
        });
        document.querySelectorAll(".act-supprimer").forEach(function (b) {
            b.addEventListener("click", function () {
                if (!confirm("Supprimer definitivement le compte de " + b.dataset.nom
                             + " et toutes ses donnees ?")) return;
                if (!confirm("Cette action est irreversible. Confirmer ?")) return;
                appeler("/api/admin/comptes/" + b.dataset.id, { method: "DELETE" }, chargerComptes);
            });
        });
    }

    // -------------------------------------------------------- securite --
    function chargerSecurite() {
        fetch("/api/admin/securite").then(function (r) { return r.json(); }).then(function (lignes) {
            var c = document.getElementById("liste-securite");
            if (!lignes.length) { c.innerHTML = vide("Aucun echec de connexion recent."); return; }
            c.innerHTML = "";
            lignes.forEach(function (l) {
                var div = document.createElement("div");
                div.className = "transaction-item";
                div.innerHTML =
                    '<div class="transaction-info">'
                    + '<span class="transaction-desc">' + esc(l.email) + "</span>"
                    + '<span class="transaction-cat"><span class="badge '
                    + (l.bloque ? "badge-red" : "badge-orange") + '">'
                    + (l.bloque ? "bloque" : "surveille") + "</span> "
                    + l.essais + " essai(s)</span>"
                    + '<span class="transaction-date">dernier essai : ' + esc(l.dernier) + "</span></div>"
                    + '<div class="transaction-actions"><button class="btn-modifier act-debloquer" data-email="'
                    + esc(l.email) + '">Debloquer</button></div>';
                c.appendChild(div);
            });
            document.querySelectorAll(".act-debloquer").forEach(function (b) {
                b.addEventListener("click", function () {
                    appeler("/api/admin/debloquer", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ email: b.dataset.email })
                    }, chargerSecurite);
                });
            });
        });
    }

    // --------------------------------------------------------- journal --
    function chargerJournal() {
        fetch("/api/admin/journal").then(function (r) { return r.json(); }).then(function (lignes) {
            var c = document.getElementById("liste-journal");
            if (!lignes.length) { c.innerHTML = vide("Aucune action enregistree pour l'instant."); return; }
            c.innerHTML = lignes.map(function (l) {
                return '<div class="transaction-item"><div class="transaction-info">'
                    + '<span class="transaction-desc">' + esc(l.action)
                    + (l.cible ? " &mdash; " + esc(l.cible) : "") + "</span>"
                    + '<span class="transaction-cat">' + esc(l.admin)
                    + (l.detail ? " &middot; " + esc(l.detail) : "") + "</span>"
                    + '<span class="transaction-date">' + esc(l.moment) + "</span>"
                    + "</div></div>";
            }).join("");
        });
    }

    // ------------------------------------------------------- demarrage --
    document.addEventListener("DOMContentLoaded", function () {
        document.getElementById("btn-menu").addEventListener("click", function () {
            document.getElementById("sidebar").classList.toggle("open");
            document.getElementById("sidebar-overlay").classList.toggle("active");
        });
        document.getElementById("sidebar-overlay").addEventListener("click", fermerMenu);
        document.getElementById("lien-logout").addEventListener("click", function (e) {
            e.preventDefault();
            fetch("/api/logout", { method: "POST" }).then(function () { window.location.href = "/"; });
        });
        document.getElementById("btn-actualiser").addEventListener("click", function () {
            var visible = document.querySelector(".page:not([style*='none'])");
            if (visible) changerVue(visible.id, document.querySelector(".sidebar a.active"));
        });
        document.getElementById("btn-chercher").addEventListener("click", chargerComptes);
        document.getElementById("recherche-compte").addEventListener("keydown", function (e) {
            if (e.key === "Enter") chargerComptes();
        });
        document.getElementById("btn-vider-recherche").addEventListener("click", function () {
            document.getElementById("recherche-compte").value = "";
            chargerComptes();
        });

        chargerStatistiques();
    });
})();

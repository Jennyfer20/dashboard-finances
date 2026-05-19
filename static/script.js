function changerPage(page) {
    var pages = document.querySelectorAll(".page");
    pages.forEach(function (p) { p.style.display = "none"; });
    document.getElementById("page-" + page).style.display = "block";

    var liens = document.querySelectorAll(".sidebar a:not(.logout-link)");
    liens.forEach(function (lien) { lien.classList.remove("active"); });
    event.target.classList.add("active");

    if (page === "transactions") {
        chargerCategories();
    }
    if (page === "parametres") {
        chargerProfil();
    }
}

function togglePasswordDash(inputId, icon) {
    var input = document.getElementById(inputId);
    if (input.type === "password") {
        input.type = "text";
        icon.textContent = "🙈";
    } else {
        input.type = "password";
        icon.textContent = "👁️";
    }
}

document.addEventListener("DOMContentLoaded", function () {

    var graphiqueDepenses = null;

    function chargerDonnees() {
        fetch("/api/resume")
            .then(function (r) { return r.json(); })
            .then(function (data) {
                document.getElementById("val-solde").textContent = data.solde.toLocaleString() + " FCFA";
                document.getElementById("val-revenus").textContent = data.revenus.toLocaleString() + " FCFA";
                document.getElementById("val-depenses").textContent = data.depenses.toLocaleString() + " FCFA";
                document.getElementById("val-transactions").textContent = data.nb_transactions;
            });

        fetch("/api/depenses-par-categorie")
            .then(function (r) { return r.json(); })
            .then(function (data) {
                var ctx = document.getElementById("graphique-depenses").getContext("2d");
                if (graphiqueDepenses) { graphiqueDepenses.destroy(); }
                graphiqueDepenses = new Chart(ctx, {
                    type: "doughnut",
                    data: {
                        labels: data.labels,
                        datasets: [{ data: data.valeurs, backgroundColor: ["#ef4444", "#f59e0b", "#3b82f6", "#10b981", "#8b5cf6", "#ec4899"] }]
                    },
                    options: { responsive: true }
                });
            });

        chargerTransactions();
    }

    window.chargerTransactions = function (filtres) {
        var url = "/api/transactions";
        if (filtres) {
            var params = [];
            if (filtres.categorie) params.push("categorie=" + filtres.categorie);
            if (filtres.date_debut) params.push("date_debut=" + filtres.date_debut);
            if (filtres.date_fin) params.push("date_fin=" + filtres.date_fin);
            if (params.length > 0) url += "?" + params.join("&");
        }

        fetch(url)
            .then(function (r) { return r.json(); })
            .then(function (data) {
                var container = document.getElementById("liste-transactions");
                container.innerHTML = "";

                if (data.length === 0) {
                    container.innerHTML = '<p style="color:#94a3b8; text-align:center; padding:20px;">Aucune transaction trouvee</p>';
                    return;
                }

                data.forEach(function (t) {
                    var div = document.createElement("div");
                    div.className = "transaction-item";
                    var signe = t.type === "revenu" ? "+" : "-";
                    var classe = t.type === "revenu" ? "montant-revenu" : "montant-depense";
                    var dateStr = t.date_ajout || "";

                    div.innerHTML =
                        '<div class="transaction-info">' +
                        '<span class="transaction-desc">' + t.description + '</span>' +
                        '<span class="transaction-cat">' + t.categorie + '</span>' +
                        '<span class="transaction-date">' + dateStr + '</span>' +
                        '</div>' +
                        '<span class="' + classe + '">' + signe + t.montant.toLocaleString() + ' FCFA</span>' +
                        '<div class="transaction-actions">' +
                        '<button class="btn-modifier" data-id="' + t.id + '" data-type="' + t.type + '" data-categorie="' + t.categorie + '" data-montant="' + t.montant + '" data-description="' + t.description + '">Modifier</button>' +
                        '<button class="btn-supprimer" data-id="' + t.id + '">Supprimer</button>' +
                        '</div>';

                    container.appendChild(div);
                });

                document.querySelectorAll(".btn-modifier").forEach(function (btn) {
                    btn.addEventListener("click", function () {
                        document.getElementById("edit-id").value = btn.dataset.id;
                        document.getElementById("edit-type").value = btn.dataset.type;
                        document.getElementById("edit-categorie").value = btn.dataset.categorie;
                        document.getElementById("edit-montant").value = btn.dataset.montant;
                        document.getElementById("edit-description").value = btn.dataset.description;
                        document.getElementById("popup-modifier").style.display = "flex";
                    });
                });

                document.querySelectorAll(".btn-supprimer").forEach(function (btn) {
                    btn.addEventListener("click", function () {
                        if (confirm("Es-tu sur de vouloir supprimer cette transaction ?")) {
                            fetch("/api/supprimer/" + btn.dataset.id, { method: "DELETE" })
                                .then(function (r) { return r.json(); })
                                .then(function (data) { if (data.succes) chargerDonnees(); });
                        }
                    });
                });
            });
    };

    window.chargerCategories = function () {
        fetch("/api/categories")
            .then(function (r) { return r.json(); })
            .then(function (cats) {
                var select = document.getElementById("filtre-categorie");
                select.innerHTML = '<option value="">Toutes les categories</option>';
                cats.forEach(function (cat) {
                    select.innerHTML += '<option value="' + cat + '">' + cat + '</option>';
                });
            });
    };

    // Charger les infos du profil
    window.chargerProfil = function () {
        fetch("/api/profil")
            .then(function (r) { return r.json(); })
            .then(function (data) {
                document.getElementById("param-nom").value = data.nom;
                document.getElementById("param-email").value = data.email;
            });
    };

    chargerDonnees();

    // Bouton Ajouter
    document.getElementById("btn-ajouter").addEventListener("click", function () {
        var type = document.getElementById("form-type").value;
        var categorie = document.getElementById("form-categorie").value;
        var montant = document.getElementById("form-montant").value;
        var description = document.getElementById("form-description").value;
        if (!categorie || !montant || !description) { alert("Remplis tous les champs !"); return; }

        fetch("/api/ajouter", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ type: type, categorie: categorie, montant: montant, description: description })
        })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data.succes) {
                    document.getElementById("form-categorie").value = "";
                    document.getElementById("form-montant").value = "";
                    document.getElementById("form-description").value = "";
                    chargerDonnees();
                }
            });
    });

    // Bouton Filtrer
    document.getElementById("btn-filtrer").addEventListener("click", function () {
        chargerTransactions({
            categorie: document.getElementById("filtre-categorie").value,
            date_debut: document.getElementById("filtre-date-debut").value,
            date_fin: document.getElementById("filtre-date-fin").value
        });
    });

    // Bouton Reset
    document.getElementById("btn-reset").addEventListener("click", function () {
        document.getElementById("filtre-categorie").value = "";
        document.getElementById("filtre-date-debut").value = "";
        document.getElementById("filtre-date-fin").value = "";
        chargerTransactions();
    });

    // Bouton Sauvegarder transaction
    document.getElementById("btn-sauvegarder").addEventListener("click", function () {
        var id = document.getElementById("edit-id").value;
        fetch("/api/modifier/" + id, {
            method: "PUT",   
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                type: document.getElementById("edit-type").value,
                categorie: document.getElementById("edit-categorie").value,
                montant: document.getElementById("edit-montant").value,
                description: document.getElementById("edit-description").value
            })
        })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data.succes) {
                    document.getElementById("popup-modifier").style.display = "none";
                    chargerDonnees();
                }
            });
    });

    // Bouton Annuler popup
    document.getElementById("btn-annuler").addEventListener("click", function () {
        document.getElementById("popup-modifier").style.display = "none";
    });

    // === PARAMETRES ===

    // Sauvegarder profil
    document.getElementById("btn-save-profil").addEventListener("click", function () {
        var nom = document.getElementById("param-nom").value;
        var email = document.getElementById("param-email").value;
        if (!nom || !email) { return; }

        fetch("/api/profil/modifier", {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ nom: nom, email: email })
        })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                var msg = document.getElementById("profil-msg");
                if (data.succes) {
                    msg.textContent = "Profil mis a jour !";
                    msg.style.color = "#10b981";
                    document.getElementById("titre-page").textContent = "Bonjour, " + nom + " 👋";
                } else {
                    msg.textContent = data.erreur;
                    msg.style.color = "#ef4444";
                }
                setTimeout(function () { msg.textContent = ""; }, 3000);
            });
    });

    // Changer mot de passe
    document.getElementById("btn-change-mdp").addEventListener("click", function () {
        var ancien = document.getElementById("param-ancien-mdp").value;
        var nouveau = document.getElementById("param-nouveau-mdp").value;
        var confirm = document.getElementById("param-confirm-mdp").value;
        var msg = document.getElementById("mdp-msg");

        if (!ancien || !nouveau || !confirm) {
            msg.textContent = "Remplis tous les champs !";
            msg.style.color = "#ef4444";
            return;
        }
        if (nouveau !== confirm) {
            msg.textContent = "Les mots de passe ne correspondent pas !";
            msg.style.color = "#ef4444";
            return;
        }

        fetch("/api/profil/mot-de-passe", {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ ancien: ancien, nouveau: nouveau })
        })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data.succes) {
                    msg.textContent = "Mot de passe change !";
                    msg.style.color = "#10b981";
                    document.getElementById("param-ancien-mdp").value = "";
                    document.getElementById("param-nouveau-mdp").value = "";
                    document.getElementById("param-confirm-mdp").value = "";
                } else {
                    msg.textContent = data.erreur;
                    msg.style.color = "#ef4444";
                }
                setTimeout(function () { msg.textContent = ""; }, 3000);
            });
    });

    // Supprimer compte
    document.getElementById("btn-supprimer-compte").addEventListener("click", function () {
        if (confirm("Es-tu VRAIMENT sur de vouloir supprimer ton compte ? Toutes tes donnees seront perdues.")) {
            if (confirm("Derniere chance ! Cette action est irreversible.")) {
                fetch("/api/profil/supprimer", { method: "DELETE" })
                    .then(function (r) { return r.json(); })
                    .then(function (data) {
                        if (data.succes) {
                            window.location.href = "/";
                        }
                    });
            }
        }
    });

    // Mode sombre
    document.getElementById("btn-sombre").addEventListener("click", function () {
        document.body.classList.add("dark");
        document.getElementById("btn-sombre").classList.add("btn-actif");
        document.getElementById("btn-clair").classList.remove("btn-actif");
    });

    document.getElementById("btn-clair").addEventListener("click", function () {
        document.body.classList.remove("dark");
        document.getElementById("btn-clair").classList.add("btn-actif");
        document.getElementById("btn-sombre").classList.remove("btn-actif");
    });

});






















































 
// === Fonction pour changer de page ===
function changerPage(page) {
    // Cacher toutes les pages
    var pages = document.querySelectorAll(".page");
    pages.forEach(function (p) {
        p.style.display = "none";
    });

    // Afficher la page demandee
    document.getElementById("page-" + page).style.display = "block";

    // Mettre a jour le titre
    var titres = {
        "dashboard": "Tableau de bord",
        "transactions": "Transactions",
        "parametres": "Parametres"
    };
    document.getElementById("titre-page").textContent = titres[page];

    // Mettre a jour le lien actif dans la sidebar
    var liens = document.querySelectorAll(".sidebar a");
    liens.forEach(function (lien) {
        lien.classList.remove("active");
    });
    event.target.classList.add("active");
}

document.addEventListener("DOMContentLoaded", function () {

    var graphiqueDepenses = null;

    // === Fonction pour charger tout ===
    function chargerDonnees() {

        // 1. Charger le resume (cartes)
        fetch("/api/resume")
            .then(function (r) { return r.json(); })
            .then(function (data) {
                document.getElementById("val-solde").textContent = data.solde.toLocaleString() + " FCFA";
                document.getElementById("val-revenus").textContent = data.revenus.toLocaleString() + " FCFA";
                document.getElementById("val-depenses").textContent = data.depenses.toLocaleString() + " FCFA";
                document.getElementById("val-transactions").textContent = data.nb_transactions;
            });

        // 2. Charger le graphique
        fetch("/api/depenses-par-categorie")
            .then(function (r) { return r.json(); })
            .then(function (data) {
                var ctx = document.getElementById("graphique-depenses").getContext("2d");

                if (graphiqueDepenses) {
                    graphiqueDepenses.destroy();
                }

                graphiqueDepenses = new Chart(ctx, {
                    type: "doughnut",
                    data: {
                        labels: data.labels,
                        datasets: [{
                            data: data.valeurs,
                            backgroundColor: ["#ef4444", "#f59e0b", "#3b82f6", "#10b981", "#8b5cf6"]
                        }]
                    },
                    options: { responsive: true }
                });
            });

        // 3. Charger la liste des transactions
        fetch("/api/transactions")
            .then(function (r) { return r.json(); })
            .then(function (data) {
                var container = document.getElementById("liste-transactions");
                container.innerHTML = "";

                data.forEach(function (t) {
                    var div = document.createElement("div");
                    div.className = "transaction-item";

                    var signe = t.type === "revenu" ? "+" : "-";
                    var classe = t.type === "revenu" ? "montant-revenu" : "montant-depense";

                    div.innerHTML =
                        '<div class="transaction-info">' +
                        '<span class="transaction-desc">' + t.description + '</span>' +
                        '<span class="transaction-cat">' + t.categorie + '</span>' +
                        '</div>' +
                        '<span class="' + classe + '">' + signe + t.montant.toLocaleString() + ' FCFA</span>' +
                        '<div class="transaction-actions">' +
                        '<button class="btn-modifier" data-id="' + t.id + '" data-type="' + t.type + '" data-categorie="' + t.categorie + '" data-montant="' + t.montant + '" data-description="' + t.description + '">Modifier</button>' +
                        '<button class="btn-supprimer" data-id="' + t.id + '">Supprimer</button>' +
                        '</div>';

                    container.appendChild(div);
                });

                // Ajouter les evenements sur les boutons Modifier
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

                // Ajouter les evenements sur les boutons Supprimer
                document.querySelectorAll(".btn-supprimer").forEach(function (btn) {
                    btn.addEventListener("click", function () {
                        if (confirm("Es-tu sur de vouloir supprimer cette transaction ?")) {
                            fetch("/api/supprimer/" + btn.dataset.id, {
                                method: "DELETE"
                            })
                                .then(function (r) { return r.json(); })
                                .then(function (data) {
                                    if (data.succes) {
                                        chargerDonnees();
                                    }
                                });
                        }
                    });
                });
            });
    }

    // Charger les donnees au demarrage
    chargerDonnees();

    // === Bouton Ajouter ===
    document.getElementById("btn-ajouter").addEventListener("click", function () {
        var type = document.getElementById("form-type").value;
        var categorie = document.getElementById("form-categorie").value;
        var montant = document.getElementById("form-montant").value;
        var description = document.getElementById("form-description").value;

        if (!categorie || !montant || !description) {
            alert("Remplis tous les champs !");
            return;
        }

        fetch("/api/ajouter", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                type: type,
                categorie: categorie,
                montant: montant,
                description: description
            })
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

    // === Bouton Sauvegarder (popup modifier) ===
    document.getElementById("btn-sauvegarder").addEventListener("click", function () {
        var id = document.getElementById("edit-id").value;
        var type = document.getElementById("edit-type").value;
        var categorie = document.getElementById("edit-categorie").value;
        var montant = document.getElementById("edit-montant").value;
        var description = document.getElementById("edit-description").value;

        fetch("/api/modifier/" + id, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                type: type,
                categorie: categorie,
                montant: montant,
                description: description
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

    // === Bouton Annuler (popup modifier) ===
    document.getElementById("btn-annuler").addEventListener("click", function () {
        document.getElementById("popup-modifier").style.display = "none";
    });

    // === Boutons Mode Clair / Sombre ===
    var btnClair = document.getElementById("btn-clair");
    var btnSombre = document.getElementById("btn-sombre");

    btnSombre.addEventListener("click", function () {
        document.body.classList.add("dark");
        btnSombre.classList.add("btn-actif");
        btnClair.classList.remove("btn-actif");
    });

    btnClair.addEventListener("click", function () {
        document.body.classList.remove("dark");
        btnClair.classList.add("btn-actif");
        btnSombre.classList.remove("btn-actif");
    });

});
// === SIDEBAR MOBILE ===
function toggleSidebar() {
    document.getElementById("sidebar").classList.toggle("open");
    document.getElementById("sidebar-overlay").classList.toggle("active");
}
function closeSidebar() {
    document.getElementById("sidebar").classList.remove("open");
    document.getElementById("sidebar-overlay").classList.remove("active");
}

function changerPage(page) {
    var pages = document.querySelectorAll(".page");
    pages.forEach(function (p) { p.style.display = "none"; });
    document.getElementById("page-" + page).style.display = "block";
    var liens = document.querySelectorAll(".sidebar a:not(.logout-link)");
    liens.forEach(function (lien) { lien.classList.remove("active"); });
    event.target.closest("a").classList.add("active");
    closeSidebar();

    if (page === "transactions") { chargerCategories(); chargerTransactions(); }
    if (page === "employes") { chargerEmployes(); }
    if (page === "salaires") { chargerSalaires(); }
    if (page === "parametres") { chargerProfil(); }
    if (page === "dashboard") { chargerDashboard(); }
}

function togglePasswordDash(inputId, icon) {
    var input = document.getElementById(inputId);
    if (input.type === "password") { input.type = "text"; icon.setAttribute("data-lucide", "eye-off"); }
    else { input.type = "password"; icon.setAttribute("data-lucide", "eye"); }
    lucide.createIcons();
}

document.addEventListener("DOMContentLoaded", function () {

    var graphiqueMensuel = null;
    var graphiqueDepenses = null;

    // Hamburger
    document.getElementById("btn-menu").addEventListener("click", toggleSidebar);
    document.getElementById("sidebar-overlay").addEventListener("click", closeSidebar);

    // === DASHBOARD ===
    window.chargerDashboard = function () {
        fetch("/api/dashboard").then(function (r) { return r.json(); }).then(function (data) {
            if (typeof USER_MODE !== 'undefined' && USER_MODE === 'entreprise') {
                document.getElementById("val-ca").textContent = (data.revenus + data.factures).toLocaleString() + " FCFA";
                document.getElementById("val-depenses").textContent = data.depenses.toLocaleString() + " FCFA";
                document.getElementById("val-benefice").textContent = data.benefice.toLocaleString() + " FCFA";
                document.getElementById("val-masse").textContent = data.masse_salariale.toLocaleString() + " FCFA";
                document.getElementById("val-employes").textContent = data.nb_employes;
                document.getElementById("val-transactions").textContent = data.nb_transactions;
            } else {
                var solde = data.revenus - data.depenses;
                if (document.getElementById("val-solde")) document.getElementById("val-solde").textContent = solde.toLocaleString() + " FCFA";
                if (document.getElementById("val-revenus-perso")) document.getElementById("val-revenus-perso").textContent = data.revenus.toLocaleString() + " FCFA";
                if (document.getElementById("val-depenses-perso")) document.getElementById("val-depenses-perso").textContent = data.depenses.toLocaleString() + " FCFA";
                if (document.getElementById("val-transactions-perso")) document.getElementById("val-transactions-perso").textContent = data.nb_transactions;
            }
        });

        fetch("/api/revenus-par-mois").then(function (r) { return r.json(); }).then(function (data) {
            var ctx = document.getElementById("graphique-mensuel").getContext("2d");
            if (graphiqueMensuel) graphiqueMensuel.destroy();
            graphiqueMensuel = new Chart(ctx, {
                type: "bar",
                data: {
                    labels: data.mois,
                    datasets: [
                        { label: "Revenus", data: data.revenus, backgroundColor: "#10b981" },
                        { label: "Depenses", data: data.depenses, backgroundColor: "#ef4444" }
                    ]
                },
                options: { responsive: true }
            });
        });

        fetch("/api/depenses-par-categorie").then(function (r) { return r.json(); }).then(function (data) {
            var ctx = document.getElementById("graphique-depenses").getContext("2d");
            if (graphiqueDepenses) graphiqueDepenses.destroy();
            graphiqueDepenses = new Chart(ctx, {
                type: "doughnut",
                data: {
                    labels: data.labels,
                    datasets: [{ data: data.valeurs, backgroundColor: ["#ef4444", "#f59e0b", "#3b82f6", "#10b981", "#8b5cf6", "#ec4899"] }]
                },
                options: { responsive: true }
            });
        });
    };

    chargerDashboard();

    // === TRANSACTIONS ===
    window.chargerTransactions = function (filtres) {
        var url = "/api/transactions";
        if (filtres) {
            var params = [];
            if (filtres.type) params.push("type=" + filtres.type);
            if (filtres.categorie) params.push("categorie=" + filtres.categorie);
            if (filtres.date_debut) params.push("date_debut=" + filtres.date_debut);
            if (filtres.date_fin) params.push("date_fin=" + filtres.date_fin);
            if (params.length > 0) url += "?" + params.join("&");
        }
        fetch(url).then(function (r) { return r.json(); }).then(function (data) {
            var container = document.getElementById("liste-transactions");
            container.innerHTML = "";
            if (data.length === 0) { container.innerHTML = '<p style="color:#94a3b8;text-align:center;padding:20px;">Aucune transaction</p>'; return; }
            data.forEach(function (t) {
                var div = document.createElement("div");
                div.className = "transaction-item";
                var signe = t.type === "depense" ? "-" : "+";
                var classe = t.type === "depense" ? "montant-depense" : "montant-revenu";
                var badge = t.type === "revenu" ? "badge-green" : t.type === "depense" ? "badge-red" : "badge-blue";
                div.innerHTML =
                    '<div class="transaction-info">' +
                    '<span class="transaction-desc">' + t.description + '</span>' +
                    '<span class="transaction-cat"><span class="badge ' + badge + '">' + t.type + '</span> ' + t.categorie + '</span>' +
                    '<span class="transaction-date">' + (t.date_ajout || "") + '</span>' +
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
                    if (confirm("Supprimer cette transaction ?")) {
                        fetch("/api/supprimer/" + btn.dataset.id, { method: "DELETE" }).then(function (r) { return r.json(); }).then(function (d) { if (d.succes) { chargerTransactions(); chargerDashboard(); } });
                    }
                });
            });
        });
    };

    window.chargerCategories = function () {
        fetch("/api/categories").then(function (r) { return r.json(); }).then(function (cats) {
            var select = document.getElementById("filtre-categorie");
            select.innerHTML = '<option value="">Toutes categories</option>';
            cats.forEach(function (c) { select.innerHTML += '<option value="' + c + '">' + c + '</option>'; });
        });
    };

    // === EMPLOYES ===
    window.chargerEmployes = function () {
        fetch("/api/employes").then(function (r) { return r.json(); }).then(function (data) {
            var container = document.getElementById("liste-employes");
            container.innerHTML = "";
            if (data.length === 0) { container.innerHTML = '<p style="color:#94a3b8;text-align:center;padding:20px;">Aucun employe</p>'; return; }
            data.forEach(function (e) {
                if (!e.actif) return;
                var div = document.createElement("div");
                div.className = "transaction-item";
                div.innerHTML =
                    '<div class="transaction-info">' +
                    '<span class="transaction-desc">' + e.nom + '</span>' +
                    '<span class="transaction-cat">' + e.poste + ' - ' + e.departement + '</span>' +
                    '<span class="transaction-date">' + (e.email || "") + ' | ' + (e.telephone || "") + '</span>' +
                    '</div>' +
                    '<span class="montant-revenu">' + e.salaire_base.toLocaleString() + ' FCFA</span>' +
                    '<div class="transaction-actions">' +
                    '<button class="btn-modifier btn-edit-emp" data-id="' + e.id + '" data-nom="' + e.nom + '" data-poste="' + e.poste + '" data-dept="' + e.departement + '" data-salaire="' + e.salaire_base + '" data-email="' + (e.email || "") + '" data-tel="' + (e.telephone || "") + '">Modifier</button>' +
                    '<button class="btn-supprimer btn-del-emp" data-id="' + e.id + '">Supprimer</button>' +
                    '</div>';
                container.appendChild(div);
            });
            document.querySelectorAll(".btn-edit-emp").forEach(function (btn) {
                btn.addEventListener("click", function () {
                    document.getElementById("edit-emp-id").value = btn.dataset.id;
                    document.getElementById("edit-emp-nom").value = btn.dataset.nom;
                    document.getElementById("edit-emp-poste").value = btn.dataset.poste;
                    document.getElementById("edit-emp-dept").value = btn.dataset.dept;
                    document.getElementById("edit-emp-salaire").value = btn.dataset.salaire;
                    document.getElementById("edit-emp-email").value = btn.dataset.email;
                    document.getElementById("edit-emp-tel").value = btn.dataset.tel;
                    document.getElementById("popup-modifier-emp").style.display = "flex";
                });
            });
            document.querySelectorAll(".btn-del-emp").forEach(function (btn) {
                btn.addEventListener("click", function () {
                    if (confirm("Supprimer cet employe ?")) {
                        fetch("/api/employes/supprimer/" + btn.dataset.id, { method: "DELETE" }).then(function (r) { return r.json(); }).then(function (d) { if (d.succes) chargerEmployes(); });
                    }
                });
            });
        });
    };

    // === SALAIRES ===
    window.chargerSalaires = function () {
        var mois = document.getElementById("sal-mois").value || "";
        var url = "/api/salaires";
        if (mois) url += "?mois=" + mois;
        fetch(url).then(function (r) { return r.json(); }).then(function (data) {
            var container = document.getElementById("liste-salaires");
            container.innerHTML = "";
            if (data.length === 0) { container.innerHTML = '<p style="color:#94a3b8;text-align:center;padding:20px;">Aucun salaire pour ce mois</p>'; return; }
            data.forEach(function (s) {
                var div = document.createElement("div");
                div.className = "transaction-item";
                var statutClass = s.statut === "paye" ? "badge-green" : "badge-orange";
                var statutText = s.statut === "paye" ? "Paye" : "En attente";
                div.innerHTML =

                    // Theme
                    document.getElementById("btn-sombre").addEventListener("click", function () {
                        document.body.classList.add("dark"); document.getElementById("btn-sombre").classList.add("btn-actif"); document.getElementById("btn-clair").classList.remove("btn-actif");
                    });
                document.getElementById("btn-clair").addEventListener("click", function () {
                    document.body.classList.remove("dark"); document.getElementById("btn-clair").classList.add("btn-actif"); document.getElementById("btn-sombre").classList.remove("btn-actif");
                });
            });
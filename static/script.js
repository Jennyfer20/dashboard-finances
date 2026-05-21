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
            document.getElementById("val-ca").textContent = (data.revenus + data.factures).toLocaleString() + " FCFA";
            document.getElementById("val-depenses").textContent = data.depenses.toLocaleString() + " FCFA";
            document.getElementById("val-benefice").textContent = data.benefice.toLocaleString() + " FCFA";
            document.getElementById("val-masse").textContent = data.masse_salariale.toLocaleString() + " FCFA";
            document.getElementById("val-employes").textContent = data.nb_employes;
            document.getElementById("val-transactions").textContent = data.nb_transactions;
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
                    '<div class="transaction-info">' +
                    '<span class="transaction-desc">' + s.employe_nom + '</span>' +
                    '<span class="transaction-cat">' + s.employe_poste + ' | ' + s.mois + '</span>' +
                    '<span class="transaction-date">Base: ' + s.montant.toLocaleString() + ' | Bonus: ' + s.bonus.toLocaleString() + ' | Ded: ' + s.deductions.toLocaleString() + '</span>' +
                    '</div>' +
                    '<span class="badge ' + statutClass + '">' + statutText + '</span>' +
                    '<span class="montant-revenu" style="margin-left:10px;">' + s.net_paye.toLocaleString() + ' FCFA</span>' +
                    (s.statut === "en_attente" ? '<div class="transaction-actions"><button class="btn-modifier btn-payer-sal" data-id="' + s.id + '">Payer</button></div>' : '');
                container.appendChild(div);
            });
            document.querySelectorAll(".btn-payer-sal").forEach(function (btn) {
                btn.addEventListener("click", function () {
                    fetch("/api/salaires/payer/" + btn.dataset.id, { method: "PUT" }).then(function (r) { return r.json(); }).then(function (d) { if (d.succes) chargerSalaires(); });
                });
            });
        });
    };

    window.chargerProfil = function () {
        fetch("/api/profil").then(function (r) { return r.json(); }).then(function (data) {
            document.getElementById("param-nom").value = data.nom;
            document.getElementById("param-email").value = data.email;
        });
    };

    // === BOUTONS ===

    // Ajouter transaction
    document.getElementById("btn-ajouter").addEventListener("click", function () {
        var type = document.getElementById("form-type").value;
        var categorie = document.getElementById("form-categorie").value;
        var montant = document.getElementById("form-montant").value;
        var description = document.getElementById("form-description").value;
        if (!categorie || !montant || !description) { alert("Remplis tous les champs !"); return; }
        fetch("/api/ajouter", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ type: type, categorie: categorie, montant: montant, description: description }) })
            .then(function (r) { return r.json(); }).then(function (d) {
                if (d.succes) { document.getElementById("form-categorie").value = ""; document.getElementById("form-montant").value = ""; document.getElementById("form-description").value = ""; chargerTransactions(); chargerDashboard(); }
            });
    });

    // Filtrer
    document.getElementById("btn-filtrer").addEventListener("click", function () {
        chargerTransactions({
            type: document.getElementById("filtre-type").value,
            categorie: document.getElementById("filtre-categorie").value,
            date_debut: document.getElementById("filtre-date-debut").value,
            date_fin: document.getElementById("filtre-date-fin").value
        });
    });

    document.getElementById("btn-reset").addEventListener("click", function () {
        document.getElementById("filtre-type").value = "";
        document.getElementById("filtre-categorie").value = "";
        document.getElementById("filtre-date-debut").value = "";
        document.getElementById("filtre-date-fin").value = "";
        chargerTransactions();
    });

    // Sauvegarder transaction modifiee
    document.getElementById("btn-sauvegarder").addEventListener("click", function () {
        var id = document.getElementById("edit-id").value;
        fetch("/api/modifier/" + id, {
            method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({
                type: document.getElementById("edit-type").value, categorie: document.getElementById("edit-categorie").value,
                montant: document.getElementById("edit-montant").value, description: document.getElementById("edit-description").value
            })
        }).then(function (r) { return r.json(); }).then(function (d) { if (d.succes) { document.getElementById("popup-modifier").style.display = "none"; chargerTransactions(); chargerDashboard(); } });
    });

    document.getElementById("btn-annuler").addEventListener("click", function () { document.getElementById("popup-modifier").style.display = "none"; });

    // Ajouter employe
    document.getElementById("btn-ajouter-emp").addEventListener("click", function () {
        var nom = document.getElementById("emp-nom").value;
        var poste = document.getElementById("emp-poste").value;
        var dept = document.getElementById("emp-dept").value;
        var salaire = document.getElementById("emp-salaire").value;
        if (!nom || !poste || !dept || !salaire) { alert("Remplis nom, poste, departement et salaire !"); return; }
        fetch("/api/employes/ajouter", {
            method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({
                nom: nom, poste: poste, departement: dept, salaire_base: salaire, email: document.getElementById("emp-email").value, telephone: document.getElementById("emp-tel").value
            })
        }).then(function (r) { return r.json(); }).then(function (d) {
            if (d.succes) { ["emp-nom", "emp-poste", "emp-dept", "emp-salaire", "emp-email", "emp-tel"].forEach(function (id) { document.getElementById(id).value = ""; }); chargerEmployes(); chargerDashboard(); }
        });
    });

    // Sauvegarder employe modifie
    document.getElementById("btn-save-emp").addEventListener("click", function () {
        var id = document.getElementById("edit-emp-id").value;
        fetch("/api/employes/modifier/" + id, {
            method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({
                nom: document.getElementById("edit-emp-nom").value, poste: document.getElementById("edit-emp-poste").value,
                departement: document.getElementById("edit-emp-dept").value, salaire_base: document.getElementById("edit-emp-salaire").value,
                email: document.getElementById("edit-emp-email").value, telephone: document.getElementById("edit-emp-tel").value
            })
        }).then(function (r) { return r.json(); }).then(function (d) { if (d.succes) { document.getElementById("popup-modifier-emp").style.display = "none"; chargerEmployes(); } });
    });

    document.getElementById("btn-annuler-emp").addEventListener("click", function () { document.getElementById("popup-modifier-emp").style.display = "none"; });

    // Generer salaires
    document.getElementById("btn-generer-sal").addEventListener("click", function () {
        var mois = document.getElementById("sal-mois").value;
        if (!mois) { alert("Choisis un mois !"); return; }
        fetch("/api/salaires/generer", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ mois: mois }) })
            .then(function (r) { return r.json(); }).then(function (d) {
                var msg = document.getElementById("sal-msg");
                if (d.succes) { msg.textContent = d.nb + " fiches generees !"; msg.style.color = "#10b981"; chargerSalaires(); }
                else { msg.textContent = d.erreur; msg.style.color = "#ef4444"; }
                setTimeout(function () { msg.textContent = ""; }, 3000);
            });
    });

    // Payer tous
    document.getElementById("btn-payer-tous").addEventListener("click", function () {
        var mois = document.getElementById("sal-mois").value;
        if (!mois) { alert("Choisis un mois !"); return; }
        if (confirm("Payer tous les salaires de " + mois + " ?")) {
            fetch("/api/salaires/payer-tous", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ mois: mois }) })
                .then(function (r) { return r.json(); }).then(function (d) { if (d.succes) chargerSalaires(); });
        }
    });

    // Profil
    document.getElementById("btn-save-profil").addEventListener("click", function () {
        fetch("/api/profil/modifier", {
            method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({
                nom: document.getElementById("param-nom").value, email: document.getElementById("param-email").value
            })
        }).then(function (r) { return r.json(); }).then(function (d) {
            var msg = document.getElementById("profil-msg");
            if (d.succes) { msg.textContent = "Profil mis a jour !"; msg.style.color = "#10b981"; document.getElementById("titre-page").textContent = "Bonjour, " + document.getElementById("param-nom").value; }
            else { msg.textContent = d.erreur; msg.style.color = "#ef4444"; }
            setTimeout(function () { msg.textContent = ""; }, 3000);
        });
    });

    // Changer MDP
    document.getElementById("btn-change-mdp").addEventListener("click", function () {
        var ancien = document.getElementById("param-ancien-mdp").value;
        var nouveau = document.getElementById("param-nouveau-mdp").value;
        var confirmMdp = document.getElementById("param-confirm-mdp").value;
        var msg = document.getElementById("mdp-msg");
        if (!ancien || !nouveau || !confirmMdp) { msg.textContent = "Remplis tous les champs !"; msg.style.color = "#ef4444"; return; }
        if (nouveau !== confirmMdp) { msg.textContent = "Les mots de passe ne correspondent pas !"; msg.style.color = "#ef4444"; return; }
        fetch("/api/profil/mot-de-passe", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ancien: ancien, nouveau: nouveau }) })
            .then(function (r) { return r.json(); }).then(function (d) {
                if (d.succes) { msg.textContent = "Mot de passe change !"; msg.style.color = "#10b981"; document.getElementById("param-ancien-mdp").value = ""; document.getElementById("param-nouveau-mdp").value = ""; document.getElementById("param-confirm-mdp").value = ""; }
                else { msg.textContent = d.erreur; msg.style.color = "#ef4444"; }
                setTimeout(function () { msg.textContent = ""; }, 3000);
            });
    });

    // Supprimer compte
    document.getElementById("btn-supprimer-compte").addEventListener("click", function () {
        if (confirm("VRAIMENT supprimer ton compte ?")) { if (confirm("Derniere chance !")) { fetch("/api/profil/supprimer", { method: "DELETE" }).then(function (r) { return r.json(); }).then(function (d) { if (d.succes) window.location.href = "/"; }); } }
    });

    // Theme
    document.getElementById("btn-sombre").addEventListener("click", function () {
        document.body.classList.add("dark"); document.getElementById("btn-sombre").classList.add("btn-actif"); document.getElementById("btn-clair").classList.remove("btn-actif");
    });
    document.getElementById("btn-clair").addEventListener("click", function () {
        document.body.classList.remove("dark"); document.getElementById("btn-clair").classList.add("btn-actif"); document.getElementById("btn-sombre").classList.remove("btn-actif");
    });
});
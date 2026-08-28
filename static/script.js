// Devise du compte, renseignee par /api/dashboard et /api/profil.
var DEVISE = "FCFA";

function montant(valeur) {
    return Number(valeur || 0).toLocaleString() + " " + DEVISE;
}

// Echappe les donnees avant insertion dans du HTML : sans cela, une
// description ou un nom d'employe contenant du balisage serait execute.
function esc(v) {
    if (v === null || v === undefined) return "";
    return String(v).replace(/[&<>"']/g, function (c) {
        return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
}
function toggleSidebar() { document.getElementById("sidebar").classList.toggle("open"); document.getElementById("sidebar-overlay").classList.toggle("active") }
function closeSidebar() { document.getElementById("sidebar").classList.remove("open"); document.getElementById("sidebar-overlay").classList.remove("active") }
function changerPage(page) { var pages = document.querySelectorAll(".page"); pages.forEach(function (p) { p.style.display = "none" }); document.getElementById("page-" + page).style.display = "block"; var liens = document.querySelectorAll(".sidebar a:not(.logout-link)"); liens.forEach(function (l) { l.classList.remove("active") }); event.target.closest("a").classList.add("active"); closeSidebar(); if (page === "transactions") { chargerCategories(); chargerTransactions() } if (page === "employes" && typeof chargerEmployes === "function") { chargerEmployes() } if (page === "salaires" && typeof chargerSalaires === "function") { chargerSalaires() } if (page === "budgets") { chargerCategories(); chargerBudgets() } if (page === "recurrences") { chargerRecurrences() } if (page === "parametres") { chargerProfil() } if (page === "dashboard") { chargerDashboard() } }
function togglePasswordDash(id, icon) { var i = document.getElementById(id); if (i.type === "password") { i.type = "text"; icon.setAttribute("data-lucide", "eye-off") } else { i.type = "password"; icon.setAttribute("data-lucide", "eye") } lucide.createIcons() }

document.addEventListener("DOMContentLoaded", function () {
    var graphiqueMensuel = null, graphiqueDepenses = null;
    document.getElementById("btn-menu").addEventListener("click", toggleSidebar);
    var lienLogout = document.getElementById("lien-logout");
    if (lienLogout) {
        lienLogout.addEventListener("click", function (e) {
            e.preventDefault();
            fetch("/api/logout", { method: "POST" }).then(function () { window.location.href = "/" });
        });
    }
    document.getElementById("sidebar-overlay").addEventListener("click", closeSidebar);
    document.getElementById("btn-refresh").addEventListener("click", function () { chargerDashboard(); var ic = this.querySelector('.icon-sm'); if (ic) { ic.style.animation = 'spin 0.5s ease'; setTimeout(function () { ic.style.animation = '' }, 500) } });

    window.chargerDashboard = function () {
        fetch("/api/dashboard").then(function (r) { return r.json() }).then(function (d) {
            if (d.devise) DEVISE = d.devise;
            if (d.recurrences_creees > 0 && typeof chargerTransactions === "function") { chargerTransactions(); }
            if (USER_MODE === "entreprise") { document.getElementById("val-ca").textContent = montant(d.revenus + d.factures); document.getElementById("val-depenses").textContent = montant(d.depenses); document.getElementById("val-benefice").textContent = montant(d.benefice); document.getElementById("val-masse").textContent = montant(d.masse_salariale); document.getElementById("val-employes").textContent = d.nb_employes; document.getElementById("val-transactions").textContent = d.nb_transactions }
            else { var s = d.revenus - d.depenses; if (document.getElementById("val-solde")) document.getElementById("val-solde").textContent = montant(s); if (document.getElementById("val-revenus-perso")) document.getElementById("val-revenus-perso").textContent = montant(d.revenus); if (document.getElementById("val-depenses-perso")) document.getElementById("val-depenses-perso").textContent = montant(d.depenses); if (document.getElementById("val-transactions-perso")) document.getElementById("val-transactions-perso").textContent = d.nb_transactions }
        });
        fetch("/api/revenus-par-mois").then(function (r) { return r.json() }).then(function (d) { var ctx = document.getElementById("graphique-mensuel").getContext("2d"); if (graphiqueMensuel) graphiqueMensuel.destroy(); graphiqueMensuel = new Chart(ctx, { type: "bar", data: { labels: d.mois, datasets: [{ label: "Revenus", data: d.revenus, backgroundColor: "#10b981" }, { label: "Depenses", data: d.depenses, backgroundColor: "#ef4444" }] }, options: { responsive: true } }) });
        fetch("/api/depenses-par-categorie").then(function (r) { return r.json() }).then(function (d) { var ctx = document.getElementById("graphique-depenses").getContext("2d"); if (graphiqueDepenses) graphiqueDepenses.destroy(); graphiqueDepenses = new Chart(ctx, { type: "doughnut", data: { labels: d.labels, datasets: [{ data: d.valeurs, backgroundColor: ["#ef4444", "#f59e0b", "#3b82f6", "#10b981", "#8b5cf6", "#ec4899"] }] }, options: { responsive: true } }) })
    };
    chargerDashboard();

    var pageCourante = 1, filtresCourants = null;

    window.chargerTransactions = function (f, page) {
        if (f !== undefined) { filtresCourants = f; pageCourante = 1; }
        if (page) pageCourante = page;
        var p = ["page=" + pageCourante];
        var fc = filtresCourants || {};
        if (fc.type) p.push("type=" + encodeURIComponent(fc.type));
        if (fc.categorie) p.push("categorie=" + encodeURIComponent(fc.categorie));
        if (fc.date_debut) p.push("date_debut=" + encodeURIComponent(fc.date_debut));
        if (fc.date_fin) p.push("date_fin=" + encodeURIComponent(fc.date_fin));
        if (fc.q) p.push("q=" + encodeURIComponent(fc.q));
        fetch("/api/transactions?" + p.join("&")).then(function (r) { return r.json() }).then(function (reponse) {
            var data = reponse.transactions || [];
            var c = document.getElementById("liste-transactions"); c.innerHTML = "";
            var infoTotal = document.getElementById("trans-total");
            if (infoTotal) infoTotal.textContent = reponse.total ? "(" + reponse.total + ")" : "";
            if (data.length === 0) { c.innerHTML = '<p style="color:#94a3b8;text-align:center;padding:20px">Aucune transaction</p>'; }
            data.forEach(function (t) {
                var div = document.createElement("div"); div.className = "transaction-item"; var sg = t.type === "depense" ? "-" : "+"; var cl = t.type === "depense" ? "montant-depense" : "montant-revenu"; var bg = t.type === "revenu" ? "badge-green" : t.type === "depense" ? "badge-red" : "badge-blue";
                div.innerHTML = '<div class="transaction-info"><span class="transaction-desc">' + esc(t.description) + '</span><span class="transaction-cat"><span class="badge ' + bg + '">' + esc(t.type) + '</span> ' + esc(t.categorie) + '</span><span class="transaction-date">' + esc(t.date_ajout) + '</span></div><span class="' + cl + '">' + sg + montant(t.montant) + '</span><div class="transaction-actions"><button class="btn-modifier" data-id="' + t.id + '" data-type="' + esc(t.type) + '" data-categorie="' + esc(t.categorie) + '" data-montant="' + t.montant + '" data-description="' + esc(t.description) + '">Modifier</button><button class="btn-supprimer" data-id="' + t.id + '">Supprimer</button></div>'; c.appendChild(div)
            });
            var info = document.getElementById("page-info");
            if (info) {
                info.textContent = "Page " + (reponse.page || 1) + " sur " + (reponse.pages || 1);
                document.getElementById("btn-page-prec").disabled = (reponse.page || 1) <= 1;
                document.getElementById("btn-page-suiv").disabled = (reponse.page || 1) >= (reponse.pages || 1);
                document.getElementById("pagination").style.display = (reponse.pages || 1) > 1 ? "flex" : "none";
            }
            document.querySelectorAll(".btn-modifier").forEach(function (b) { b.addEventListener("click", function () { document.getElementById("edit-id").value = b.dataset.id; document.getElementById("edit-type").value = b.dataset.type; document.getElementById("edit-categorie").value = b.dataset.categorie; document.getElementById("edit-montant").value = b.dataset.montant; document.getElementById("edit-description").value = b.dataset.description; document.getElementById("popup-modifier").style.display = "flex" }) });
            document.querySelectorAll(".btn-supprimer").forEach(function (b) { b.addEventListener("click", function () { if (confirm("Supprimer ?")) { fetch("/api/supprimer/" + b.dataset.id, { method: "DELETE" }).then(function (r) { return r.json() }).then(function (d) { if (d.succes) { chargerTransactions(); chargerDashboard() } }) } }) })
        })
    };

    window.chargerCategories = function () { fetch("/api/categories").then(function (r) { return r.json() }).then(function (cats) { var s = document.getElementById("filtre-categorie"); s.innerHTML = '<option value="">Toutes categories</option>'; cats.forEach(function (c) { s.innerHTML += '<option value="' + esc(c) + '">' + esc(c) + '</option>' });
        var dl = document.getElementById("liste-categories");
        if (dl) { dl.innerHTML = ""; cats.forEach(function (c) { dl.innerHTML += '<option value="' + esc(c) + '"></option>' }) } }) };

    if (USER_MODE === "entreprise") {
        window.chargerEmployes = function () {
            fetch("/api/employes").then(function (r) { return r.json() }).then(function (data) {
                var c = document.getElementById("liste-employes"); c.innerHTML = ""; if (data.length === 0) { c.innerHTML = '<p style="color:#94a3b8;text-align:center;padding:20px">Aucun employe</p>'; return }
                data.forEach(function (e) {
                    if (!e.actif) return; var div = document.createElement("div"); div.className = "transaction-item";
                    div.innerHTML = '<div class="transaction-info"><span class="transaction-desc">' + esc(e.nom) + '</span><span class="transaction-cat">' + esc(e.poste) + ' - ' + esc(e.departement) + '</span><span class="transaction-date">' + esc(e.email) + ' | ' + esc(e.telephone) + '</span></div><span class="montant-revenu">' + montant(e.salaire_base) + '</span><div class="transaction-actions"><button class="btn-modifier btn-edit-emp" data-id="' + e.id + '" data-nom="' + esc(e.nom) + '" data-poste="' + esc(e.poste) + '" data-dept="' + esc(e.departement) + '" data-salaire="' + e.salaire_base + '" data-email="' + esc(e.email) + '" data-tel="' + esc(e.telephone) + '">Modifier</button><button class="btn-supprimer btn-del-emp" data-id="' + e.id + '">Supprimer</button></div>'; c.appendChild(div)
                });
                document.querySelectorAll(".btn-edit-emp").forEach(function (b) { b.addEventListener("click", function () { document.getElementById("edit-emp-id").value = b.dataset.id; document.getElementById("edit-emp-nom").value = b.dataset.nom; document.getElementById("edit-emp-poste").value = b.dataset.poste; document.getElementById("edit-emp-dept").value = b.dataset.dept; document.getElementById("edit-emp-salaire").value = b.dataset.salaire; document.getElementById("edit-emp-email").value = b.dataset.email; document.getElementById("edit-emp-tel").value = b.dataset.tel; document.getElementById("popup-modifier-emp").style.display = "flex" }) });
                document.querySelectorAll(".btn-del-emp").forEach(function (b) { b.addEventListener("click", function () { if (confirm("Supprimer ?")) { fetch("/api/employes/supprimer/" + b.dataset.id, { method: "DELETE" }).then(function (r) { return r.json() }).then(function (d) { if (d.succes) chargerEmployes() }) } }) })
            })
        };
        window.chargerSalaires = function () {
            var m = document.getElementById("sal-mois").value || ""; var url = "/api/salaires"; if (m) url += "?mois=" + m;
            fetch(url).then(function (r) { return r.json() }).then(function (data) {
                var c = document.getElementById("liste-salaires"); c.innerHTML = ""; if (data.length === 0) { c.innerHTML = '<p style="color:#94a3b8;text-align:center;padding:20px">Aucun salaire</p>'; return }
                data.forEach(function (s) {
                    var div = document.createElement("div"); div.className = "transaction-item"; var sc = s.statut === "paye" ? "badge-green" : "badge-orange"; var st = s.statut === "paye" ? "Paye" : "En attente";
                    div.innerHTML = '<div class="transaction-info"><span class="transaction-desc">' + esc(s.employe_nom) + '</span><span class="transaction-cat">' + esc(s.employe_poste) + ' | ' + esc(s.mois) + '</span><span class="transaction-date">Base: ' + s.montant.toLocaleString() + ' | Bonus: ' + s.bonus.toLocaleString() + ' | Ded: ' + s.deductions.toLocaleString() + '</span></div><span class="badge ' + sc + '">' + st + '</span><span class="montant-revenu" style="margin-left:10px">' + montant(s.net_paye) + '</span><div class="transaction-actions">' + (s.statut === "en_attente" ? '<button class="btn-modifier btn-edit-sal" data-id="' + s.id + '" data-base="' + s.montant + '" data-bonus="' + s.bonus + '" data-ded="' + s.deductions + '" data-nom="' + esc(s.employe_nom) + '">Bonus</button><button class="btn-modifier btn-payer-sal" data-id="' + s.id + '">Payer</button>' : '') + '<a href="/api/salaires/pdf/' + s.id + '" class="btn-modifier" style="text-decoration:none" target="_blank">PDF</a></div>'; c.appendChild(div)
                });
                document.querySelectorAll(".btn-edit-sal").forEach(function (b) { b.addEventListener("click", function () {
                    document.getElementById("edit-sal-id").value = b.dataset.id;
                    document.getElementById("edit-sal-bonus").value = b.dataset.bonus;
                    document.getElementById("edit-sal-deductions").value = b.dataset.ded;
                    document.getElementById("edit-sal-info").textContent = b.dataset.nom + " - salaire de base " + montant(b.dataset.base);
                    document.getElementById("edit-sal-id").dataset.base = b.dataset.base;
                    document.getElementById("edit-sal-msg").textContent = "";
                    majNetSalaire();
                    document.getElementById("popup-modifier-sal").style.display = "flex";
                }) });
                document.querySelectorAll(".btn-payer-sal").forEach(function (b) { b.addEventListener("click", function () { fetch("/api/salaires/payer/" + b.dataset.id, { method: "PUT" }).then(function (r) { return r.json() }).then(function (d) { if (d.succes) chargerSalaires() }) }) })
            })
        };
        document.getElementById("btn-ajouter-emp").addEventListener("click", function () { var n = document.getElementById("emp-nom").value, p = document.getElementById("emp-poste").value, d = document.getElementById("emp-dept").value, s = document.getElementById("emp-salaire").value; if (!n || !p || !d || !s) { alert("Remplis les champs !"); return } fetch("/api/employes/ajouter", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ nom: n, poste: p, departement: d, salaire_base: s, email: document.getElementById("emp-email").value, telephone: document.getElementById("emp-tel").value }) }).then(function (r) { return r.json() }).then(function (x) { if (x.succes) { ["emp-nom", "emp-poste", "emp-dept", "emp-salaire", "emp-email", "emp-tel"].forEach(function (i) { document.getElementById(i).value = "" }); chargerEmployes(); chargerDashboard() } }) });
        document.getElementById("btn-save-emp").addEventListener("click", function () { var id = document.getElementById("edit-emp-id").value; fetch("/api/employes/modifier/" + id, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ nom: document.getElementById("edit-emp-nom").value, poste: document.getElementById("edit-emp-poste").value, departement: document.getElementById("edit-emp-dept").value, salaire_base: document.getElementById("edit-emp-salaire").value, email: document.getElementById("edit-emp-email").value, telephone: document.getElementById("edit-emp-tel").value }) }).then(function (r) { return r.json() }).then(function (d) { if (d.succes) { document.getElementById("popup-modifier-emp").style.display = "none"; chargerEmployes() } }) });
        document.getElementById("btn-annuler-emp").addEventListener("click", function () { document.getElementById("popup-modifier-emp").style.display = "none" });
        document.getElementById("btn-generer-sal").addEventListener("click", function () { var m = document.getElementById("sal-mois").value; if (!m) { alert("Choisis un mois !"); return } fetch("/api/salaires/generer", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ mois: m }) }).then(function (r) { return r.json() }).then(function (d) { var msg = document.getElementById("sal-msg"); if (d.succes) { msg.textContent = d.nb + " fiches !"; msg.style.color = "#10b981"; chargerSalaires() } else { msg.textContent = d.erreur; msg.style.color = "#ef4444" } setTimeout(function () { msg.textContent = "" }, 3000) }) });
        document.getElementById("btn-payer-tous").addEventListener("click", function () { var m = document.getElementById("sal-mois").value; if (!m) { alert("Choisis un mois !"); return } if (confirm("Payer tous ?")) { fetch("/api/salaires/payer-tous", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ mois: m }) }).then(function (r) { return r.json() }).then(function (d) { if (d.succes) chargerSalaires() }) } })
    }

    // ---------------------------------------------------------- budgets --
    window.chargerBudgets = function () {
        var champMois = document.getElementById("budget-mois");
        var url = "/api/budgets";
        if (champMois && champMois.value) url += "?mois=" + encodeURIComponent(champMois.value);
        fetch(url).then(function (r) { return r.json() }).then(function (d) {
            if (d.devise) DEVISE = d.devise;
            var c = document.getElementById("liste-budgets"); c.innerHTML = "";
            if (!d.budgets || d.budgets.length === 0) {
                c.innerHTML = '<p style="color:#94a3b8;text-align:center;padding:20px">Aucun budget defini. Ajoute une categorie ci-dessus pour suivre tes depenses.</p>';
                return;
            }
            d.budgets.forEach(function (b) {
                var largeur = Math.min(100, b.pourcentage);
                var couleur = b.depasse ? "#ef4444" : (b.pourcentage >= 80 ? "#f59e0b" : "#10b981");
                var div = document.createElement("div"); div.className = "transaction-item";
                div.style.flexDirection = "column"; div.style.alignItems = "stretch"; div.style.gap = "8px";
                div.innerHTML = '<div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px">'
                    + '<span class="transaction-desc">' + esc(b.categorie) + '</span>'
                    + '<span style="color:' + couleur + ';font-weight:600">' + montant(b.depense) + ' / ' + montant(b.montant_mensuel) + '</span></div>'
                    + '<div style="background:#e2e8f0;border-radius:6px;height:10px;overflow:hidden"><div style="width:' + largeur + '%;height:100%;background:' + couleur + '"></div></div>'
                    + '<div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px">'
                    + '<span style="font-size:0.85rem;color:' + couleur + '">' + (b.depasse ? "Depassement de " + montant(-b.restant) : "Reste " + montant(b.restant)) + ' (' + b.pourcentage + '%)</span>'
                    + '<button class="btn-supprimer btn-del-budget" data-id="' + b.id + '">Supprimer</button></div>';
                c.appendChild(div);
            });
            document.querySelectorAll(".btn-del-budget").forEach(function (b) {
                b.addEventListener("click", function () {
                    if (confirm("Supprimer ce budget ?")) {
                        fetch("/api/budgets/supprimer/" + b.dataset.id, { method: "DELETE" })
                            .then(function (r) { return r.json() }).then(function (x) { if (x.succes) chargerBudgets() });
                    }
                });
            });
        })
    };

    var champBudgetMois = document.getElementById("budget-mois");
    if (champBudgetMois) champBudgetMois.addEventListener("change", function () { chargerBudgets() });

    var btnBudget = document.getElementById("btn-ajouter-budget");
    if (btnBudget) btnBudget.addEventListener("click", function () {
        var cat = document.getElementById("budget-categorie").value;
        var mnt = document.getElementById("budget-montant").value;
        var msg = document.getElementById("budget-msg");
        if (!cat || !mnt) { msg.textContent = "Renseigne la categorie et le plafond."; msg.style.color = "#ef4444"; return }
        fetch("/api/budgets/enregistrer", { method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ categorie: cat, montant_mensuel: mnt }) })
            .then(function (r) { return r.json() }).then(function (d) {
                if (d.succes) {
                    document.getElementById("budget-categorie").value = "";
                    document.getElementById("budget-montant").value = "";
                    msg.textContent = "Budget enregistre."; msg.style.color = "#10b981";
                    chargerBudgets();
                } else { msg.textContent = d.erreur || "Erreur"; msg.style.color = "#ef4444" }
                setTimeout(function () { msg.textContent = "" }, 3000);
            })
    });

    // ------------------------------------------------------- echeances --
    window.chargerRecurrences = function () {
        fetch("/api/recurrences").then(function (r) { return r.json() }).then(function (data) {
            var c = document.getElementById("liste-recurrences"); c.innerHTML = "";
            if (data.length === 0) {
                c.innerHTML = '<p style="color:#94a3b8;text-align:center;padding:20px">Aucune echeance. Ajoute un loyer ou un abonnement pour ne plus le ressaisir chaque mois.</p>';
                return;
            }
            data.forEach(function (r) {
                var cl = r.type === "depense" ? "montant-depense" : "montant-revenu";
                var bg = r.type === "revenu" ? "badge-green" : r.type === "depense" ? "badge-red" : "badge-blue";
                var div = document.createElement("div"); div.className = "transaction-item";
                if (!r.actif) div.style.opacity = "0.55";
                div.innerHTML = '<div class="transaction-info"><span class="transaction-desc">' + esc(r.description) + '</span>'
                    + '<span class="transaction-cat"><span class="badge ' + bg + '">' + esc(r.type) + '</span> ' + esc(r.categorie) + '</span>'
                    + '<span class="transaction-date">Le ' + r.jour_mois + ' de chaque mois' + (r.actif ? '' : ' - en pause') + '</span></div>'
                    + '<span class="' + cl + '">' + montant(r.montant) + '</span>'
                    + '<div class="transaction-actions"><button class="btn-modifier btn-toggle-rec" data-id="' + r.id + '">' + (r.actif ? "Mettre en pause" : "Reactiver") + '</button>'
                    + '<button class="btn-supprimer btn-del-rec" data-id="' + r.id + '">Supprimer</button></div>';
                c.appendChild(div);
            });
            document.querySelectorAll(".btn-toggle-rec").forEach(function (b) {
                b.addEventListener("click", function () {
                    fetch("/api/recurrences/basculer/" + b.dataset.id, { method: "PUT" })
                        .then(function (r) { return r.json() }).then(function (d) { if (d.succes) chargerRecurrences() });
                });
            });
            document.querySelectorAll(".btn-del-rec").forEach(function (b) {
                b.addEventListener("click", function () {
                    if (confirm("Supprimer cette echeance ?")) {
                        fetch("/api/recurrences/supprimer/" + b.dataset.id, { method: "DELETE" })
                            .then(function (r) { return r.json() }).then(function (d) { if (d.succes) chargerRecurrences() });
                    }
                });
            });
        })
    };

    var btnRec = document.getElementById("btn-ajouter-rec");
    if (btnRec) btnRec.addEventListener("click", function () {
        var msg = document.getElementById("rec-msg");
        var corps = {
            type: document.getElementById("rec-type").value,
            categorie: document.getElementById("rec-categorie").value,
            montant: document.getElementById("rec-montant").value,
            description: document.getElementById("rec-description").value,
            jour_mois: document.getElementById("rec-jour").value
        };
        if (!corps.categorie || !corps.montant || !corps.description) {
            msg.textContent = "Remplis la categorie, le montant et la description."; msg.style.color = "#ef4444"; return;
        }
        fetch("/api/recurrences/ajouter", { method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify(corps) })
            .then(function (r) { return r.json() }).then(function (d) {
                if (d.succes) {
                    ["rec-categorie", "rec-montant", "rec-description"].forEach(function (i) { document.getElementById(i).value = "" });
                    msg.textContent = "Echeance enregistree."; msg.style.color = "#10b981";
                    chargerRecurrences();
                } else { msg.textContent = d.erreur || "Erreur"; msg.style.color = "#ef4444" }
                setTimeout(function () { msg.textContent = "" }, 3000);
            })
    });

    // --------------------------------------------- export et pagination --
    var btnExport = document.getElementById("btn-export");
    if (btnExport) btnExport.addEventListener("click", function () { window.location.href = "/api/transactions/export.csv" });

    var btnPrec = document.getElementById("btn-page-prec");
    if (btnPrec) btnPrec.addEventListener("click", function () { if (pageCourante > 1) chargerTransactions(undefined, pageCourante - 1) });
    var btnSuiv = document.getElementById("btn-page-suiv");
    if (btnSuiv) btnSuiv.addEventListener("click", function () { chargerTransactions(undefined, pageCourante + 1) });

    // ------------------------------------------- bonus et deductions -----
    window.majNetSalaire = function () {
        var base = Number(document.getElementById("edit-sal-id").dataset.base || 0);
        var bonus = Number(document.getElementById("edit-sal-bonus").value || 0);
        var ded = Number(document.getElementById("edit-sal-deductions").value || 0);
        document.getElementById("edit-sal-net").textContent = "Net a payer : " + montant(base + bonus - ded);
    };
    ["edit-sal-bonus", "edit-sal-deductions"].forEach(function (id) {
        var champ = document.getElementById(id);
        if (champ) champ.addEventListener("input", majNetSalaire);
    });
    var btnSaveSal = document.getElementById("btn-save-sal");
    if (btnSaveSal) btnSaveSal.addEventListener("click", function () {
        var id = document.getElementById("edit-sal-id").value;
        var msg = document.getElementById("edit-sal-msg");
        fetch("/api/salaires/modifier/" + id, { method: "PUT", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ bonus: document.getElementById("edit-sal-bonus").value,
                                   deductions: document.getElementById("edit-sal-deductions").value }) })
            .then(function (r) { return r.json() }).then(function (d) {
                if (d.succes) { document.getElementById("popup-modifier-sal").style.display = "none"; chargerSalaires(); chargerDashboard() }
                else { msg.textContent = d.erreur || "Erreur"; msg.style.color = "#ef4444" }
            })
    });
    var btnAnnulerSal = document.getElementById("btn-annuler-sal");
    if (btnAnnulerSal) btnAnnulerSal.addEventListener("click", function () { document.getElementById("popup-modifier-sal").style.display = "none" });

    document.getElementById("btn-ajouter").addEventListener("click", function () { var t = document.getElementById("form-type").value, c = document.getElementById("form-categorie").value, m = document.getElementById("form-montant").value, d = document.getElementById("form-description").value; if (!c || !m || !d) { alert("Remplis tout !"); return } fetch("/api/ajouter", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ type: t, categorie: c, montant: m, description: d }) }).then(function (r) { return r.json() }).then(function (x) { if (x.succes) { document.getElementById("form-categorie").value = ""; document.getElementById("form-montant").value = ""; document.getElementById("form-description").value = ""; chargerTransactions(); chargerDashboard() } }) });
    document.getElementById("btn-filtrer").addEventListener("click", function () { chargerTransactions({ type: document.getElementById("filtre-type").value, categorie: document.getElementById("filtre-categorie").value, date_debut: document.getElementById("filtre-date-debut").value, date_fin: document.getElementById("filtre-date-fin").value, q: document.getElementById("filtre-recherche").value }) });
    document.getElementById("btn-reset").addEventListener("click", function () { document.getElementById("filtre-type").value = ""; document.getElementById("filtre-categorie").value = ""; document.getElementById("filtre-date-debut").value = ""; document.getElementById("filtre-date-fin").value = ""; document.getElementById("filtre-recherche").value = ""; chargerTransactions({}) });
    document.getElementById("filtre-recherche").addEventListener("keydown", function (e) { if (e.key === "Enter") document.getElementById("btn-filtrer").click() });
    document.getElementById("btn-sauvegarder").addEventListener("click", function () { var id = document.getElementById("edit-id").value; fetch("/api/modifier/" + id, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ type: document.getElementById("edit-type").value, categorie: document.getElementById("edit-categorie").value, montant: document.getElementById("edit-montant").value, description: document.getElementById("edit-description").value }) }).then(function (r) { return r.json() }).then(function (d) { if (d.succes) { document.getElementById("popup-modifier").style.display = "none"; chargerTransactions(); chargerDashboard() } }) });
    document.getElementById("btn-annuler").addEventListener("click", function () { document.getElementById("popup-modifier").style.display = "none" });
    window.chargerProfil = function () { fetch("/api/profil").then(function (r) { return r.json() }).then(function (d) { document.getElementById("param-nom").value = d.nom; document.getElementById("param-email").value = d.email; if (d.devise) { DEVISE = d.devise; var sd = document.getElementById("param-devise"); if (sd) sd.value = d.devise } }) };
    document.getElementById("btn-save-profil").addEventListener("click", function () { fetch("/api/profil/modifier", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ nom: document.getElementById("param-nom").value, email: document.getElementById("param-email").value, devise: document.getElementById("param-devise").value }) }).then(function (r) { return r.json() }).then(function (d) { var m = document.getElementById("profil-msg"); if (d.succes) { m.textContent = "OK !"; m.style.color = "#10b981"; DEVISE = document.getElementById("param-devise").value; document.getElementById("titre-page").textContent = "Bonjour, " + document.getElementById("param-nom").value; chargerDashboard() } else { m.textContent = d.erreur; m.style.color = "#ef4444" } setTimeout(function () { m.textContent = "" }, 3000) }) });
    document.getElementById("btn-change-mdp").addEventListener("click", function () { var a = document.getElementById("param-ancien-mdp").value, n = document.getElementById("param-nouveau-mdp").value, c = document.getElementById("param-confirm-mdp").value, m = document.getElementById("mdp-msg"); if (!a || !n || !c) { m.textContent = "Remplis tout !"; m.style.color = "#ef4444"; return } if (n !== c) { m.textContent = "Ne correspondent pas !"; m.style.color = "#ef4444"; return } fetch("/api/profil/mot-de-passe", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ancien: a, nouveau: n }) }).then(function (r) { return r.json() }).then(function (d) { if (d.succes) { m.textContent = "OK !"; m.style.color = "#10b981"; document.getElementById("param-ancien-mdp").value = ""; document.getElementById("param-nouveau-mdp").value = ""; document.getElementById("param-confirm-mdp").value = "" } else { m.textContent = d.erreur; m.style.color = "#ef4444" } setTimeout(function () { m.textContent = "" }, 3000) }) });
    document.getElementById("btn-supprimer-compte").addEventListener("click", function () { if (confirm("VRAIMENT ?")) { if (confirm("Derniere chance !")) { fetch("/api/profil/supprimer", { method: "DELETE" }).then(function (r) { return r.json() }).then(function (d) { if (d.succes) window.location.href = "/" }) } } });
});
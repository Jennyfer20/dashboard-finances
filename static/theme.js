/* Theme clair / sombre, partage par toutes les pages.
 *
 * Ce fichier est charge dans le <head>, avant le rendu : la classe est posee
 * sur <html> des la premiere ligne, ce qui evite l'eclair blanc au chargement
 * d'une page en mode sombre.
 *
 * Le choix est conserve dans le navigateur. Sans choix enregistre, on suit la
 * preference du systeme d'exploitation.
 */
(function () {
    "use strict";

    var CLE = "budgetlab-theme";

    function lireChoix() {
        try {
            return localStorage.getItem(CLE);
        } catch (e) {
            // Navigation privee ou stockage refuse : on continue sans memoire.
            return null;
        }
    }

    function ecrireChoix(theme) {
        try {
            localStorage.setItem(CLE, theme);
        } catch (e) { /* sans consequence : seule la persistance est perdue */ }
    }

    function themeSysteme() {
        return (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches)
            ? "sombre" : "clair";
    }

    function themeActuel() {
        return lireChoix() || themeSysteme();
    }

    function appliquer(theme) {
        document.documentElement.classList.toggle("dark", theme === "sombre");
        // Harmonise la barre d'adresse des navigateurs mobiles.
        var meta = document.querySelector('meta[name="theme-color"]');
        if (meta) meta.setAttribute("content", theme === "sombre" ? "#0b1220" : "#2563eb");
    }

    // Applique immediatement, avant que la page ne s'affiche.
    appliquer(themeActuel());

    function majBoutons(theme) {
        var sombre = theme === "sombre";
        var bClair = document.getElementById("btn-clair");
        var bSombre = document.getElementById("btn-sombre");
        if (bClair) bClair.classList.toggle("btn-actif", !sombre);
        if (bSombre) bSombre.classList.toggle("btn-actif", sombre);

        document.querySelectorAll("[data-bascule-theme]").forEach(function (b) {
            b.setAttribute("aria-pressed", sombre ? "true" : "false");
            b.setAttribute("title", sombre ? "Passer en mode clair" : "Passer en mode sombre");
            var icone = b.querySelector("i, svg");
            if (icone) {
                icone.setAttribute("data-lucide", sombre ? "sun" : "moon");
                if (window.lucide) lucide.createIcons();
            }
        });
    }

    function definir(theme) {
        appliquer(theme);
        ecrireChoix(theme);
        majBoutons(theme);
    }

    window.themeBudgetLab = {
        definir: definir,
        actuel: themeActuel,
        basculer: function () { definir(themeActuel() === "sombre" ? "clair" : "sombre"); }
    };

    document.addEventListener("DOMContentLoaded", function () {
        majBoutons(themeActuel());

        // Bouton unique present sur les pages publiques.
        document.querySelectorAll("[data-bascule-theme]").forEach(function (b) {
            b.addEventListener("click", function (e) {
                e.preventDefault();
                window.themeBudgetLab.basculer();
            });
        });

        // Boutons Clair / Sombre du tableau de bord.
        var bClair = document.getElementById("btn-clair");
        var bSombre = document.getElementById("btn-sombre");
        if (bClair) bClair.addEventListener("click", function () { definir("clair"); });
        if (bSombre) bSombre.addEventListener("click", function () { definir("sombre"); });
    });

    // Suit le systeme tant que l'utilisateur n'a pas choisi lui-meme.
    if (window.matchMedia) {
        var requete = window.matchMedia("(prefers-color-scheme: dark)");
        var surChangement = function () {
            if (!lireChoix()) { appliquer(themeSysteme()); majBoutons(themeSysteme()); }
        };
        if (requete.addEventListener) requete.addEventListener("change", surChangement);
        else if (requete.addListener) requete.addListener(surChangement);
    }
})();

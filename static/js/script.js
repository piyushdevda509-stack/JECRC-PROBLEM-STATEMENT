document.addEventListener("DOMContentLoaded", () => {
    const hamburger = document.getElementById("hamburger");
    const headerNav = document.querySelector(".header-nav");
    const overlay = document.getElementById("sidebar-overlay");

    function toggleSidebar() {
        headerNav.classList.toggle("active");
        overlay.classList.toggle("active");
        hamburger.classList.toggle("active"); // animate hamburger
    }

    hamburger?.addEventListener("click", toggleSidebar);
    overlay?.addEventListener("click", toggleSidebar);

    // Flash messages auto-hide
    const flashMessages = document.querySelectorAll('.flash');
    flashMessages.forEach(flash => {
        setTimeout(() => {
            flash.style.transition = "opacity 0.8s";
            flash.style.opacity = "0";
            setTimeout(() => flash.remove(), 800);
        }, 4000);
    });

    // Filters
    const searchBox = document.getElementById("searchBox");
    const branchFilter = document.getElementById("branchFilter");
    const skillFilter = document.getElementById("skillFilter");
    const problems = document.querySelectorAll(".problem-card");

    function filterProblems() {
        const searchText = searchBox?.value.toLowerCase() || "";
        const branchValue = branchFilter?.value || "all";
        const skillValue = skillFilter?.value || "all";

        problems.forEach(card => {
            const title = card.dataset.title?.toLowerCase() || "";
            const desc = card.dataset.description?.toLowerCase() || "";
            const branch = card.dataset.branch || "";
            const skill = card.dataset.skill || "";

            const matchesSearch = title.includes(searchText) || desc.includes(searchText);
            const matchesBranch = branchValue === "all" || branch === branchValue;
            const matchesSkill = skillValue === "all" || skill === skillValue;

            card.style.display = (matchesSearch && matchesBranch && matchesSkill) ? "block" : "none";
        });
    }

    searchBox?.addEventListener("input", filterProblems);
    branchFilter?.addEventListener("change", filterProblems);
    skillFilter?.addEventListener("change", filterProblems);
});

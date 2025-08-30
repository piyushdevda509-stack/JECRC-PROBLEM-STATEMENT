// Wait until DOM is ready
document.addEventListener("DOMContentLoaded", () => {

    // === Flash message auto-hide ===
    const flashMessages = document.querySelectorAll('.flash');
    if (flashMessages.length) {
        setTimeout(() => {
            flashMessages.forEach(flash => {
                flash.style.transition = "opacity 0.8s";
                flash.style.opacity = "0";
                setTimeout(() => flash.remove(), 800);
            });
        }, 4000); // auto hide after 4s
    }

    // === Problem Search & Filters ===
    const searchBox = document.getElementById("searchBox");
    const branchFilter = document.getElementById("branchFilter");
    const skillFilter = document.getElementById("skillFilter");
    const problems = document.querySelectorAll(".problem-card");

    function filterProblems() {
        const searchText = searchBox?.value.toLowerCase() || "";
        const branchValue = branchFilter?.value || "all";
        const skillValue = skillFilter?.value || "all";

        problems.forEach(card => {
            const title = card.dataset.title.toLowerCase();
            const desc = card.dataset.description.toLowerCase();
            const branch = card.dataset.branch;
            const skill = card.dataset.skill;

            const matchesSearch = title.includes(searchText) || desc.includes(searchText);
            const matchesBranch = branchValue === "all" || branch === branchValue;
            const matchesSkill = skillValue === "all" || skill === skillValue;

            card.style.display = (matchesSearch && matchesBranch && matchesSkill) ? "block" : "none";
        });
    }

    // Event listeners
    searchBox?.addEventListener("input", filterProblems);
    branchFilter?.addEventListener("change", filterProblems);
    skillFilter?.addEventListener("change", filterProblems);

});

// Wait until DOM is ready
document.addEventListener("DOMContentLoaded", () => {

    // === Flash message auto-hide ===
    setTimeout(() => {
        document.querySelectorAll('.flash').forEach(flash => {
            flash.style.transition = "opacity 1s";
            flash.style.opacity = "0";
            setTimeout(() => flash.remove(), 1000);
        });
    }, 5000);

    // === Problem Search & Filters ===
    const searchBox = document.getElementById("searchBox");
    const branchFilter = document.getElementById("branchFilter");
    const skillFilter = document.getElementById("skillFilter");
    const problems = document.querySelectorAll(".problem-card");

    function filterProblems() {
        const searchText = searchBox ? searchBox.value.toLowerCase() : "";
        const branchValue = branchFilter ? branchFilter.value : "all";
        const skillValue = skillFilter ? skillFilter.value : "all";

        problems.forEach(card => {
            const title = card.dataset.title.toLowerCase();
            const desc = card.dataset.description.toLowerCase();
            const branch = card.dataset.branch;
            const skill = card.dataset.skill;

            const matchesSearch =
                title.includes(searchText) || desc.includes(searchText);
            const matchesBranch =
                branchValue === "all" || branch === branchValue;
            const matchesSkill =
                skillValue === "all" || skill === skillValue;

            if (matchesSearch && matchesBranch && matchesSkill) {
                card.style.display = "block";
            } else {
                card.style.display = "none";
            }
        });
    }

    if (searchBox) searchBox.addEventListener("input", filterProblems);
    if (branchFilter) branchFilter.addEventListener("change", filterProblems);
    if (skillFilter) skillFilter.addEventListener("change", filterProblems);


});

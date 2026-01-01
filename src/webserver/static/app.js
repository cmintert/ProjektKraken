const state = {
    availableTags: [],
    selectedTags: new Set(),
    dropdownIndex: -1
};

const dom = {
    wrapper: document.getElementById('tag-input-wrapper'),
    input: document.getElementById('tag-input'),
    dropdown: document.getElementById('tag-dropdown'),
    resetBtn: document.getElementById('reset-filter'),
    status: document.getElementById('filter-status'),
    content: document.getElementById('longform-content')
};

// --- Initialization ---

async function init() {
    await fetchTags();
    fetchLongform(); // Initial load
    attachEventListeners();
}

// --- Event Listeners ---

function attachEventListeners() {
    // Input Handling
    if (dom.input) {
        dom.input.addEventListener('focus', () => showDropdown());
        dom.input.addEventListener('input', (e) => {
            showDropdown(e.target.value);
        });

        dom.input.addEventListener('keydown', (e) => {
            if (e.key === 'Backspace' && dom.input.value === '' && state.selectedTags.size > 0) {
                // Remove last tag
                const lastTag = Array.from(state.selectedTags).pop();
                removeTag(lastTag);
            } else if (e.key === 'Enter') {
                e.preventDefault();
                selectHighlightedOption();
            } else if (e.key === 'ArrowDown') {
                e.preventDefault();
                navigateDropdown(1);
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                navigateDropdown(-1);
            }
        });
    }

    // Wrapper Focus
    if (dom.wrapper) {
        dom.wrapper.addEventListener('click', () => {
            if (dom.input) dom.input.focus();
        });
    }

    // Reset Button
    if (dom.resetBtn) {
        dom.resetBtn.addEventListener('click', () => {
            state.selectedTags.clear();
            state.dropdownIndex = -1;
            if (dom.input) dom.input.value = '';
            renderChips();
            fetchLongform(); // Auto-apply reset
        });
    }

    // Close dropdown on outside click
    document.addEventListener('click', (e) => {
        if (dom.wrapper && dom.dropdown && !dom.wrapper.contains(e.target) && !dom.dropdown.contains(e.target)) {
            hideDropdown();
        }
    });
}

// --- Logic ---

async function fetchTags() {
    try {
        const response = await fetch('/api/tags');
        const data = await response.json();
        state.availableTags = data.tags || [];
    } catch (error) {
        console.error("Failed to fetch tags:", error);
    }
}

function addTag(tag) {
    if (state.selectedTags.has(tag)) return;
    state.selectedTags.add(tag);
    if (dom.input) dom.input.value = '';
    renderChips();
    hideDropdown();
    // Auto-apply
    fetchLongform();
}

function removeTag(tag) {
    state.selectedTags.delete(tag);
    renderChips();
    // Auto-apply
    fetchLongform();
}

// --- Rendering ---

function renderChips() {
    if (!dom.wrapper) return;

    // Clear existing chips (keep input)
    const chips = dom.wrapper.querySelectorAll('.tag-chip');
    chips.forEach(chip => chip.remove());

    // Insert chips before input
    state.selectedTags.forEach(tag => {
        const chip = document.createElement('div');
        chip.className = 'tag-chip';
        chip.innerHTML = `${tag} <span class="close-btn">&times;</span>`;
        chip.querySelector('.close-btn').addEventListener('click', (e) => {
            e.stopPropagation();
            removeTag(tag);
        });
        dom.wrapper.insertBefore(chip, dom.input);
    });
}

function showDropdown(filterText = '') {
    if (!dom.dropdown) return;

    const lowerFilter = filterText.toLowerCase();
    // Filter available tags: exclude selected ones, match filter text
    const candidates = state.availableTags.filter(tag =>
        !state.selectedTags.has(tag) &&
        tag.toLowerCase().includes(lowerFilter)
    );

    if (candidates.length === 0) {
        hideDropdown();
        return;
    }

    state.filteredCandidates = candidates; // Store for keyboard nav
    dom.dropdown.innerHTML = '';
    state.dropdownIndex = 0; // Reset selection

    candidates.forEach((tag, index) => {
        const div = document.createElement('div');
        div.className = `tag-option ${index === 0 ? 'highlighted' : ''}`;
        div.textContent = tag;
        div.addEventListener('click', () => {
            addTag(tag);
            if (dom.input) dom.input.focus();
        });
        dom.dropdown.appendChild(div);
    });

    dom.dropdown.classList.add('visible');
}

function hideDropdown() {
    if (dom.dropdown) dom.dropdown.classList.remove('visible');
    state.dropdownIndex = -1;
}

function navigateDropdown(direction) {
    if (!dom.dropdown || !state.filteredCandidates || state.filteredCandidates.length === 0) return;
    const options = dom.dropdown.children;

    // Remove current highlight
    if (state.dropdownIndex >= 0 && state.dropdownIndex < options.length) {
        options[state.dropdownIndex].classList.remove('highlighted');
    }

    state.dropdownIndex += direction;
    if (state.dropdownIndex < 0) state.dropdownIndex = options.length - 1;
    if (state.dropdownIndex >= options.length) state.dropdownIndex = 0;

    // Add new highlight
    options[state.dropdownIndex].classList.add('highlighted');
    options[state.dropdownIndex].scrollIntoView({ block: 'nearest' });
}

function selectHighlightedOption() {
    if (state.dropdownIndex !== -1 && state.filteredCandidates && state.filteredCandidates[state.dropdownIndex]) {
        addTag(state.filteredCandidates[state.dropdownIndex]);
    }
}

// --- Data Fetching ---

async function fetchLongform() {
    // Show filter status immediately
    const filterCount = state.selectedTags.size;

    const params = new URLSearchParams();
    if (filterCount > 0) {
        if (dom.wrapper) dom.wrapper.style.borderColor = "var(--accent-color)";
        const filterConfig = {
            include: Array.from(state.selectedTags),
            include_mode: 'any'
        };
        params.append('filter_json', JSON.stringify(filterConfig));
    } else {
        if (dom.wrapper) dom.wrapper.style.borderColor = "var(--border-color)";
    }

    try {
        const response = await fetch(`/api/longform?${params.toString()}`);
        const data = await response.json();

        let htmlContent = '';
        const tocContainer = document.getElementById('toc');
        if (tocContainer) tocContainer.innerHTML = '<ul></ul>';
        const tocList = tocContainer ? tocContainer.querySelector('ul') : null;

        if (data.sections && Array.isArray(data.sections)) {
            htmlContent = data.sections.map((section, index) => {
                const sectionId = `section-${index}`;

                // Determine type class
                const typeClass = section.table ? `type-${section.table}` : 'type-unknown';

                // Update TOC
                if (tocList) {
                    const li = document.createElement('li');
                    const a = document.createElement('a');
                    a.href = `#${sectionId}`;
                    a.textContent = section.title || `Section ${index + 1}`;
                    li.appendChild(a);
                    tocList.appendChild(li);
                }

                return `<div id="${sectionId}" class="story-section ${typeClass}">${section.html}</div>`;
            }).join('');
        } else {
            // Fallback if structure is different
            console.warn("Unexpected data structure", data);
            htmlContent = "<p>No content found.</p>";
        }

        if (dom.content) dom.content.innerHTML = htmlContent;

        // Update status text
        if (dom.status) {
            if (filterCount > 0) {
                // Count items actually rendered
                const renderedItems = data.sections ? data.sections.length : 0;
                dom.status.textContent = `Showing ${renderedItems} items (Filtered by tags)`;
                dom.status.style.display = 'inline';
            } else {
                dom.status.style.display = 'none';
            }
        }
    } catch (error) {
        console.error("Error fetching longform:", error);
        if (dom.content) dom.content.innerHTML = "<p>Error loading content.</p>";
    }
}

// Start
document.addEventListener('DOMContentLoaded', init);

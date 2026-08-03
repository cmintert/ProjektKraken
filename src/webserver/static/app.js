/* =========================================================================
   ProjektKraken Longform Web Viewer
   Vanilla JS (no framework). All theme values come from /api/theme and are
   applied as CSS custom properties on :root.
   ========================================================================= */

const THEME_KEY_MAP = {
    app_bg: '--app-bg',
    surface: '--surface',
    border: '--border',
    primary: '--primary',
    accent_secondary: '--accent-secondary',
    text_main: '--text-main',
    text_dim: '--text-dim',
    error: '--error',
    destructive: '--destructive',
    scrollbar_bg: '--scrollbar-bg',
    scrollbar_handle: '--scrollbar-handle',
    event_main: '--event-main',
    entity_main: '--entity-main',
    font_size_h1: '--font-size-h1',
    font_size_h2: '--font-size-h2',
    font_size_h3: '--font-size-h3',
    font_size_body: '--font-size-body',
};

const THEME_LABELS = {
    dark_mode: 'Dark',
    light_mode: 'Light',
    fantasy_mode: 'Fantasy',
    imperial_mode: 'Imperial',
    cyberpunk_mode: 'Cyberpunk',
    muted_light_mode: 'Muted Light',
};

const state = {
    availableTags: [],
    includeTags: new Set(),
    excludeTags: new Set(),
    includeMode: 'any',
    excludeMode: 'any',
    caseSensitive: false,
    sections: [],
    searchMatches: [],
    searchCursor: -1,
    allThemes: {},
    activeTheme: window.__INITIAL_THEME__ || 'dark_mode',
    activeCombo: null,          // 'include' | 'exclude' | null
    dropdownIndex: -1,
    filteredCandidates: [],
    tocObserver: null,
    lanAccess: window.__LAN_ACCESS__ || false,
    accessCode: '',
};

const dom = {};

/* =========================================================================
   Init
   ========================================================================= */
document.addEventListener('DOMContentLoaded', init);

async function init() {
    cacheDom();
    attachAccessGate();
    if (state.lanAccess) {
        state.accessCode = sessionStorage.getItem('krakenLanAccessCode') || '';
        if (!state.accessCode) {
            showAccessGate();
            return;
        }
        const authenticated = await verifyAccessCode();
        if (!authenticated) return;
    }
    await loadApplication();
}

async function loadApplication() {
    await fetchTheme();
    applyTheme(state.activeTheme);
    populateThemeSwitcher();
    await fetchTags();
    attachEventListeners();
    await fetchLongform();
}

function cacheDom() {
    dom.tagWrapper = document.getElementById('tag-input-wrapper');
    dom.tagInput = document.getElementById('tag-input');
    dom.tagDropdown = document.getElementById('tag-dropdown');
    dom.excludeWrapper = document.getElementById('exclude-input-wrapper');
    dom.excludeInput = document.getElementById('exclude-input');
    dom.excludeDropdown = document.getElementById('exclude-dropdown');
    dom.includeMode = document.getElementById('include-mode');
    dom.excludeMode = document.getElementById('exclude-mode');
    dom.caseSensitive = document.getElementById('case-sensitive');
    dom.resetBtn = document.getElementById('reset-filter');
    dom.filterStatus = document.getElementById('filter-status');
    dom.status = document.getElementById('status');
    dom.content = document.getElementById('longform-content');
    dom.toc = document.getElementById('toc');
    dom.contentPanel = document.getElementById('content-panel');
    dom.emptyState = document.getElementById('empty-state');
    dom.emptyMessage = document.getElementById('empty-message');
    dom.emptyReset = document.getElementById('empty-reset');
    dom.itemCount = document.getElementById('item-count');
    dom.themeSwitcher = document.getElementById('theme-switcher');
    dom.searchToggle = document.getElementById('search-toggle');
    dom.searchBar = document.getElementById('search-bar');
    dom.searchInput = document.getElementById('search-input');
    dom.searchPrev = document.getElementById('search-prev');
    dom.searchNext = document.getElementById('search-next');
    dom.searchClose = document.getElementById('search-close');
    dom.searchCount = document.getElementById('search-count');
    dom.accessGate = document.getElementById('access-gate');
    dom.accessForm = document.getElementById('access-form');
    dom.accessCode = document.getElementById('access-code');
    dom.accessError = document.getElementById('access-error');
}

/* =========================================================================
   LAN access
   ========================================================================= */
function attachAccessGate() {
    if (!dom.accessForm) return;
    dom.accessForm.addEventListener('submit', async (event) => {
        event.preventDefault();
        const code = (dom.accessCode.value || '').replace(/\s/g, '');
        if (!/^\d{8}$/.test(code)) {
            setAccessError('Enter the complete eight-digit access code.');
            return;
        }
        state.accessCode = code;
        setAccessError('Checking code…');
        const authenticated = await verifyAccessCode();
        if (!authenticated) return;
        sessionStorage.setItem('krakenLanAccessCode', code);
        hideAccessGate();
        await loadApplication();
    });
}

async function verifyAccessCode() {
    try {
        const resp = await apiFetch('/api/theme');
        if (resp.status === 429) {
            const retryAfter = resp.headers.get('Retry-After') || '60';
            setAccessError(`Too many attempts. Try again in ${retryAfter} seconds.`);
            showAccessGate();
            return false;
        }
        if (!resp.ok) {
            setAccessError('That access code is not valid.');
            state.accessCode = '';
            sessionStorage.removeItem('krakenLanAccessCode');
            showAccessGate();
            return false;
        }
        return true;
    } catch (error) {
        console.error('Could not verify LAN access:', error);
        setAccessError('Could not reach the ProjektKraken server.');
        showAccessGate();
        return false;
    }
}

function showAccessGate() {
    if (!dom.accessGate) return;
    dom.accessGate.classList.remove('hidden');
    if (dom.accessCode) dom.accessCode.focus();
}

function hideAccessGate() {
    if (dom.accessGate) dom.accessGate.classList.add('hidden');
    setAccessError('');
}

function setAccessError(message) {
    if (dom.accessError) dom.accessError.textContent = message;
}

async function apiFetch(url, options = {}) {
    const headers = new Headers(options.headers || {});
    if (state.lanAccess && state.accessCode) {
        headers.set('Authorization', `Bearer ${state.accessCode}`);
    }
    return fetch(url, { ...options, headers });
}

/* =========================================================================
   Theme
   ========================================================================= */
async function fetchTheme() {
    try {
        const resp = await apiFetch('/api/theme');
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();
        state.allThemes = data.themes || {};
        if (data.active_theme) state.activeTheme = data.active_theme;
    } catch (e) {
        console.error('Failed to fetch theme:', e);
    }
}

function applyTheme(themeName) {
    const theme = state.allThemes[themeName];
    if (!theme) return;
    const root = document.documentElement;
    for (const [themeKey, cssVar] of Object.entries(THEME_KEY_MAP)) {
        if (theme[themeKey] !== undefined) {
            root.style.setProperty(cssVar, theme[themeKey]);
        }
    }
    state.activeTheme = themeName;
    if (dom.themeSwitcher) dom.themeSwitcher.value = themeName;
}

function populateThemeSwitcher() {
    if (!dom.themeSwitcher) return;
    dom.themeSwitcher.innerHTML = '';
    const names = Object.keys(state.allThemes);
    if (names.length === 0) {
        const opt = document.createElement('option');
        opt.value = state.activeTheme;
        opt.textContent = THEME_LABELS[state.activeTheme] || state.activeTheme;
        dom.themeSwitcher.appendChild(opt);
        return;
    }
    for (const name of names) {
        const opt = document.createElement('option');
        opt.value = name;
        opt.textContent = THEME_LABELS[name] || name;
        dom.themeSwitcher.appendChild(opt);
    }
    dom.themeSwitcher.value = state.activeTheme;
}

/* =========================================================================
   Event listeners
   ========================================================================= */
function attachEventListeners() {
    attachTagCombo('include', dom.tagWrapper, dom.tagInput, dom.tagDropdown,
        state.includeTags);
    attachTagCombo('exclude', dom.excludeWrapper, dom.excludeInput,
        dom.excludeDropdown, state.excludeTags);

    if (dom.includeMode) {
        dom.includeMode.addEventListener('click', () => toggleMode('include'));
    }
    if (dom.excludeMode) {
        dom.excludeMode.addEventListener('click', () => toggleMode('exclude'));
    }

    if (dom.caseSensitive) {
        dom.caseSensitive.addEventListener('change', (e) => {
            state.caseSensitive = e.target.checked;
            fetchLongform();
        });
    }

    if (dom.resetBtn) {
        dom.resetBtn.addEventListener('click', resetFilters);
    }
    if (dom.emptyReset) {
        dom.emptyReset.addEventListener('click', resetFilters);
    }

    document.addEventListener('click', (e) => {
        const inIncludeCombo =
            (dom.tagWrapper && dom.tagWrapper.contains(e.target)) ||
            (dom.tagDropdown && dom.tagDropdown.contains(e.target));
        const inExcludeCombo =
            (dom.excludeWrapper && dom.excludeWrapper.contains(e.target)) ||
            (dom.excludeDropdown && dom.excludeDropdown.contains(e.target));
        if (!inIncludeCombo && !inExcludeCombo) hideAllDropdowns();
    });

    if (dom.themeSwitcher) {
        dom.themeSwitcher.addEventListener('change', (e) => {
            applyTheme(e.target.value);
        });
    }

    if (dom.searchToggle) {
        dom.searchToggle.addEventListener('click', toggleSearchBar);
    }
    if (dom.searchClose) {
        dom.searchClose.addEventListener('click', hideSearchBar);
    }
    if (dom.searchInput) {
        dom.searchInput.addEventListener('input', () => {
            performSearch(dom.searchInput.value);
        });
        dom.searchInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                navigateSearch(e.shiftKey ? -1 : 1);
            } else if (e.key === 'Escape') {
                hideSearchBar();
            }
        });
    }
    if (dom.searchPrev) {
        dom.searchPrev.addEventListener('click', () => navigateSearch(-1));
    }
    if (dom.searchNext) {
        dom.searchNext.addEventListener('click', () => navigateSearch(1));
    }

    document.addEventListener('keydown', (e) => {
        const isCtrlF = (e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'f';
        if (isCtrlF) {
            e.preventDefault();
            if (dom.searchBar.classList.contains('hidden')) {
                showSearchBar();
            } else {
                dom.searchInput.focus();
                dom.searchInput.select();
            }
        } else if (e.key === 'Escape' && !dom.searchBar.classList.contains('hidden')) {
            hideSearchBar();
        }
    });
}

/* =========================================================================
   Tag combobox (shared between include and exclude)
   ========================================================================= */
function attachTagCombo(kind, wrapper, input, dropdown, tagSet) {
    if (!wrapper || !input || !dropdown) return;

    input.addEventListener('focus', () => {
        state.activeCombo = kind;
        showDropdown(input.value);
    });
    input.addEventListener('input', (e) => {
        state.activeCombo = kind;
        showDropdown(e.target.value);
    });
    input.addEventListener('keydown', (e) => {
        if (e.key === 'Backspace' && input.value === '' && tagSet.size > 0) {
            const last = Array.from(tagSet).pop();
            tagSet.delete(last);
            renderChips(wrapper, input, tagSet, kind);
            fetchLongform();
        } else if (e.key === 'Enter') {
            e.preventDefault();
            selectHighlightedOption();
        } else if (e.key === 'ArrowDown') {
            e.preventDefault();
            navigateDropdown(1);
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            navigateDropdown(-1);
        } else if (e.key === 'Escape') {
            hideAllDropdowns();
            input.blur();
        }
    });

    wrapper.addEventListener('click', (e) => {
        if (e.target === wrapper) input.focus();
    });
}

function showDropdown(filterText = '') {
    const kind = state.activeCombo;
    if (!kind) return;
    const dropdown = kind === 'include' ? dom.tagDropdown : dom.excludeDropdown;
    const tagSet = kind === 'include' ? state.includeTags : state.excludeTags;
    if (!dropdown) return;

    const lowerFilter = filterText.toLowerCase();
    const candidates = state.availableTags.filter(tag =>
        !tagSet.has(tag) &&
        tag.toLowerCase().includes(lowerFilter)
    );

    if (candidates.length === 0) {
        hideAllDropdowns();
        return;
    }

    state.filteredCandidates = candidates;
    state.dropdownIndex = 0;
    dropdown.innerHTML = '';
    candidates.forEach((tag, index) => {
        const div = document.createElement('div');
        div.className = `tag-option${index === 0 ? ' highlighted' : ''}`;
        div.textContent = tag;
        div.addEventListener('mousedown', (e) => {
            e.preventDefault();
            selectTag(tag);
        });
        dropdown.appendChild(div);
    });
    dropdown.classList.remove('hidden');
}

function hideAllDropdowns() {
    if (dom.tagDropdown) dom.tagDropdown.classList.add('hidden');
    if (dom.excludeDropdown) dom.excludeDropdown.classList.add('hidden');
    state.dropdownIndex = -1;
    state.filteredCandidates = [];
}

function navigateDropdown(direction) {
    const dropdown = state.activeCombo === 'include' ? dom.tagDropdown : dom.excludeDropdown;
    if (!dropdown || state.filteredCandidates.length === 0) return;
    const options = dropdown.children;

    if (state.dropdownIndex >= 0 && state.dropdownIndex < options.length) {
        options[state.dropdownIndex].classList.remove('highlighted');
    }
    state.dropdownIndex += direction;
    if (state.dropdownIndex < 0) state.dropdownIndex = options.length - 1;
    if (state.dropdownIndex >= options.length) state.dropdownIndex = 0;
    const opt = options[state.dropdownIndex];
    if (opt) {
        opt.classList.add('highlighted');
        opt.scrollIntoView({ block: 'nearest' });
    }
}

function selectHighlightedOption() {
    if (state.dropdownIndex < 0) return;
    const tag = state.filteredCandidates[state.dropdownIndex];
    if (tag) selectTag(tag);
}

function selectTag(tag) {
    const kind = state.activeCombo;
    if (!kind) return;
    const tagSet = kind === 'include' ? state.includeTags : state.excludeTags;
    const wrapper = kind === 'include' ? dom.tagWrapper : dom.excludeWrapper;
    const input = kind === 'include' ? dom.tagInput : dom.excludeInput;
    if (tagSet.has(tag)) return;
    tagSet.add(tag);
    input.value = '';
    renderChips(wrapper, input, tagSet, kind);
    hideAllDropdowns();
    fetchLongform();
    input.focus();
}

function renderChips(wrapper, input, tagSet, kind) {
    if (!wrapper || !input) return;
    wrapper.querySelectorAll('.tag-chip').forEach(c => c.remove());
    for (const tag of tagSet) {
        const chip = document.createElement('div');
        chip.className = 'tag-chip';
        chip.textContent = tag;
        const close = document.createElement('span');
        close.className = 'close-btn';
        close.innerHTML = '&times;';
        close.addEventListener('mousedown', (e) => {
            e.preventDefault();
            e.stopPropagation();
            tagSet.delete(tag);
            renderChips(wrapper, input, tagSet, kind);
            fetchLongform();
        });
        chip.appendChild(close);
        wrapper.insertBefore(chip, input);
    }
}

/* =========================================================================
   Filter mode toggles & reset
   ========================================================================= */
function toggleMode(kind) {
    const btn = kind === 'include' ? dom.includeMode : dom.excludeMode;
    if (!btn) return;
    const current = btn.dataset.mode || 'any';
    const next = current === 'any' ? 'all' : 'any';
    btn.dataset.mode = next;
    btn.textContent = next.toUpperCase();
    btn.classList.toggle('active-all', next === 'all');
    if (kind === 'include') state.includeMode = next;
    else state.excludeMode = next;
    const tagSet = kind === 'include' ? state.includeTags : state.excludeTags;
    if (tagSet.size > 0) fetchLongform();
}

function resetFilters() {
    state.includeTags.clear();
    state.excludeTags.clear();
    state.includeMode = 'any';
    state.excludeMode = 'any';
    state.caseSensitive = false;
    if (dom.caseSensitive) dom.caseSensitive.checked = false;
    if (dom.includeMode) {
        dom.includeMode.dataset.mode = 'any';
        dom.includeMode.textContent = 'ANY';
        dom.includeMode.classList.remove('active-all');
    }
    if (dom.excludeMode) {
        dom.excludeMode.dataset.mode = 'any';
        dom.excludeMode.textContent = 'ANY';
        dom.excludeMode.classList.remove('active-all');
    }
    if (dom.tagInput) dom.tagInput.value = '';
    if (dom.excludeInput) dom.excludeInput.value = '';
    renderChips(dom.tagWrapper, dom.tagInput, state.includeTags, 'include');
    renderChips(dom.excludeWrapper, dom.excludeInput, state.excludeTags, 'exclude');
    fetchLongform();
}

/* =========================================================================
   Data fetching
   ========================================================================= */
async function fetchTags() {
    try {
        const resp = await apiFetch('/api/tags');
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();
        state.availableTags = data.tags || [];
    } catch (e) {
        console.error('Failed to fetch tags:', e);
    }
}

function buildFilterJson() {
    const config = {};
    if (state.includeTags.size > 0) {
        config.include = Array.from(state.includeTags);
        config.include_mode = state.includeMode;
    }
    if (state.excludeTags.size > 0) {
        config.exclude = Array.from(state.excludeTags);
        config.exclude_mode = state.excludeMode;
    }
    if (state.caseSensitive) config.case_sensitive = true;
    return Object.keys(config).length > 0 ? JSON.stringify(config) : null;
}

async function fetchLongform() {
    setStatus('Loading…', 'loading');
    clearSearchHighlights();

    const params = new URLSearchParams();
    const filterJson = buildFilterJson();
    if (filterJson) params.append('filter_json', filterJson);

    try {
        const resp = await apiFetch(`/api/longform?${params.toString()}`);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();
        renderSections(data.sections || []);
        updateFilterStatus();
        setStatus('Ready', 'ready');
    } catch (e) {
        console.error('Error fetching longform:', e);
        setStatus('Error', 'error');
        if (dom.content) dom.content.innerHTML = '';
        showEmptyState('Could not load content. Check the server log.');
    }
}

function setStatus(msg, cls) {
    if (!dom.status) return;
    dom.status.textContent = msg;
    dom.status.classList.remove('ready', 'error', 'loading');
    if (cls) dom.status.classList.add(cls);
}

function updateFilterStatus() {
    if (!dom.filterStatus) return;
    const total = state.includeTags.size + state.excludeTags.size;
    if (total === 0 && !state.caseSensitive) {
        dom.filterStatus.textContent = '';
        dom.filterStatus.classList.remove('active');
    } else {
        const parts = [];
        if (state.includeTags.size > 0) {
            parts.push(`+${state.includeTags.size} (${state.includeMode})`);
        }
        if (state.excludeTags.size > 0) {
            parts.push(`-${state.excludeTags.size} (${state.excludeMode})`);
        }
        if (state.caseSensitive) parts.push('Aa');
        dom.filterStatus.textContent = `Filter: ${parts.join(' ')}`;
        dom.filterStatus.classList.add('active');
    }
}

/* =========================================================================
   Rendering
   ========================================================================= */
function renderSections(sections) {
    state.sections = sections;
    if (!dom.content || !dom.toc) return;

    if (!sections || sections.length === 0) {
        dom.content.innerHTML = '';
        dom.toc.innerHTML = '';
        if (dom.itemCount) dom.itemCount.textContent = '0 items';
        const hasFilter = state.includeTags.size > 0 ||
            state.excludeTags.size > 0 || state.caseSensitive;
        showEmptyState(hasFilter
            ? 'No items match your current filter.'
            : 'The document is empty. Create events or entities in the app.');
        return;
    }
    hideEmptyState();

    // Build title → anchor map for WikiLink resolution
    const titleToAnchor = {};
    sections.forEach((s, i) => {
        if (s.title) titleToAnchor[s.title.toLowerCase()] = `section-${i}`;
    });

    // Build content
    const contentParts = [];
    const tocParts = ['<ul>'];
    sections.forEach((section, i) => {
        const sectionId = `section-${i}`;
        const typeClass = section.table ? `type-${section.table}` : '';
        const levelClass = `toc-level-${section.heading_level || 1}`;
        const titleText = escapeHtml(section.title || `Section ${i + 1}`);

        tocParts.push(
            `<li><a href="#${sectionId}" class="${levelClass}" ` +
            `data-section="${i}">${titleText}</a></li>`
        );

        let dateHtml = '';
        if (section.table === 'events' &&
            section.lore_date !== null && section.lore_date !== undefined) {
            const start = Number(section.lore_date).toFixed(1);
            const dur = Number(section.lore_duration || 0);
            let label = `Day ${start}`;
            if (dur > 0) {
                const end = (Number(section.lore_date) + dur).toFixed(1);
                label += ` \u2013 Day ${end}`;
            }
            dateHtml = `<p class="event-date-subtitle">${escapeHtml(label)}</p>`;
        }

        const resolvedHtml = resolveWikilinks(section.html || '', titleToAnchor);
        const combined = injectDateAfterHeading(resolvedHtml, dateHtml);
        contentParts.push(
            `<div id="${sectionId}" class="story-section ${typeClass}">${combined}</div>`
        );
    });
    tocParts.push('</ul>');

    dom.content.innerHTML = contentParts.join('');
    dom.toc.innerHTML = tocParts.join('');

    if (dom.itemCount) {
        const n = sections.length;
        dom.itemCount.textContent = `${n} item${n !== 1 ? 's' : ''}`;
    }

    attachTocClickHandlers();
    setupTocObserver();
}

function injectDateAfterHeading(html, dateHtml) {
    if (!dateHtml) return html;
    const match = html.match(/<h[1-6][^>]*>[\s\S]*?<\/h[1-6]>/);
    if (!match) return dateHtml + html;
    const idx = match.index + match[0].length;
    return html.slice(0, idx) + dateHtml + html.slice(idx);
}

function resolveWikilinks(html, titleToAnchor) {
    if (!html.includes('wikilink')) return html;
    const parser = new DOMParser();
    const doc = parser.parseFromString(`<div id="root">${html}</div>`, 'text/html');
    const root = doc.getElementById('root');
    if (!root) return html;
    root.querySelectorAll('a.wikilink').forEach(el => {
        const target = (el.getAttribute('data-target') || '').trim();
        const label = el.textContent;
        const anchor = titleToAnchor[target.toLowerCase()];
        if (anchor) {
            el.setAttribute('href', `#${anchor}`);
            el.removeAttribute('data-target');
            el.classList.remove('wikilink');
            el.classList.add('wikilink-anchor');
        } else {
            const span = doc.createElement('span');
            span.className = 'wikilink-no-target';
            span.textContent = label;
            el.replaceWith(span);
        }
    });
    return root.innerHTML;
}

function attachTocClickHandlers() {
    if (!dom.toc) return;
    dom.toc.querySelectorAll('a').forEach(a => {
        a.addEventListener('click', (e) => {
            e.preventDefault();
            const target = document.querySelector(a.getAttribute('href'));
            if (target) {
                target.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        });
    });
}

function setupTocObserver() {
    if (state.tocObserver) state.tocObserver.disconnect();
    if (!dom.contentPanel) return;
    state.tocObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            const link = document.querySelector(
                `#toc a[href="#${entry.target.id}"]`);
            if (link) link.classList.toggle('active', entry.isIntersecting);
        });
    }, {
        root: dom.contentPanel,
        rootMargin: '-10% 0px -70% 0px',
        threshold: 0,
    });
    document.querySelectorAll('.story-section').forEach(el =>
        state.tocObserver.observe(el));
}

function showEmptyState(message) {
    if (!dom.emptyState) return;
    if (dom.emptyMessage && message) dom.emptyMessage.textContent = message;
    dom.emptyState.classList.remove('hidden');
}

function hideEmptyState() {
    if (dom.emptyState) dom.emptyState.classList.add('hidden');
}

/* =========================================================================
   In-page text search
   ========================================================================= */
function toggleSearchBar() {
    if (dom.searchBar.classList.contains('hidden')) {
        showSearchBar();
    } else {
        hideSearchBar();
    }
}

function showSearchBar() {
    if (!dom.searchBar) return;
    dom.searchBar.classList.remove('hidden');
    dom.searchInput.focus();
    dom.searchInput.select();
}

function hideSearchBar() {
    if (!dom.searchBar) return;
    dom.searchBar.classList.add('hidden');
    clearSearchHighlights();
    if (dom.searchCount) dom.searchCount.textContent = '';
}

function performSearch(query) {
    clearSearchHighlights();
    if (!query || !query.trim()) {
        if (dom.searchCount) dom.searchCount.textContent = '';
        return;
    }
    const caseSensitive = state.caseSensitive;
    const needle = caseSensitive ? query : query.toLowerCase();
    const root = dom.content;
    if (!root) return;

    // Two-pass: collect ranges first, then mutate DOM in reverse order.
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
        acceptNode: (n) => {
            if (!n.nodeValue || !n.nodeValue.trim()) return NodeFilter.FILTER_REJECT;
            // Skip content inside <mark> (shouldn't exist yet, defensive)
            if (n.parentElement && n.parentElement.closest('mark.search-hit')) {
                return NodeFilter.FILTER_REJECT;
            }
            return NodeFilter.FILTER_ACCEPT;
        },
    });

    const hits = [];  // [{node, start, end}]
    let node = walker.nextNode();
    while (node) {
        const text = node.nodeValue;
        const hay = caseSensitive ? text : text.toLowerCase();
        let idx = hay.indexOf(needle);
        while (idx !== -1) {
            hits.push({ node, start: idx, end: idx + needle.length });
            idx = hay.indexOf(needle, idx + needle.length);
        }
        node = walker.nextNode();
    }

    // Apply in reverse per-node order so offsets stay valid
    // Group by node then apply ranges in descending start order.
    const byNode = new Map();
    for (const hit of hits) {
        if (!byNode.has(hit.node)) byNode.set(hit.node, []);
        byNode.get(hit.node).push(hit);
    }

    const marks = [];
    for (const nodeHits of byNode.values()) {
        nodeHits.sort((a, b) => b.start - a.start);
        for (const h of nodeHits) {
            try {
                const range = document.createRange();
                range.setStart(h.node, h.start);
                range.setEnd(h.node, h.end);
                const mark = document.createElement('mark');
                mark.className = 'search-hit';
                range.surroundContents(mark);
                marks.push(mark);
            } catch {
                // surroundContents throws when the range crosses tag
                // boundaries (e.g., a match split by <em>). Skip silently.
            }
        }
    }

    // Sort marks in document order
    marks.sort((a, b) => {
        const pos = a.compareDocumentPosition(b);
        if (pos & Node.DOCUMENT_POSITION_FOLLOWING) return -1;
        if (pos & Node.DOCUMENT_POSITION_PRECEDING) return 1;
        return 0;
    });

    state.searchMatches = marks;
    state.searchCursor = marks.length > 0 ? 0 : -1;
    if (marks.length > 0) navigateSearch(0);
    updateSearchCount();
}

function navigateSearch(direction) {
    if (state.searchMatches.length === 0) {
        if (dom.searchCount) dom.searchCount.textContent = '0 / 0';
        return;
    }
    if (direction !== 0) {
        state.searchCursor =
            (state.searchCursor + direction + state.searchMatches.length) %
            state.searchMatches.length;
    }
    state.searchMatches.forEach((m, i) =>
        m.classList.toggle('active-hit', i === state.searchCursor));
    const active = state.searchMatches[state.searchCursor];
    if (active) active.scrollIntoView({ behavior: 'smooth', block: 'center' });
    updateSearchCount();
}

function updateSearchCount() {
    if (!dom.searchCount) return;
    if (state.searchMatches.length === 0) {
        dom.searchCount.textContent = dom.searchInput.value ? 'No results' : '';
    } else {
        dom.searchCount.textContent =
            `${state.searchCursor + 1} / ${state.searchMatches.length}`;
    }
}

function clearSearchHighlights() {
    document.querySelectorAll('mark.search-hit').forEach(m => {
        const parent = m.parentNode;
        if (!parent) return;
        while (m.firstChild) parent.insertBefore(m.firstChild, m);
        parent.removeChild(m);
        parent.normalize();
    });
    state.searchMatches = [];
    state.searchCursor = -1;
}

/* =========================================================================
   Utilities
   ========================================================================= */
function escapeHtml(s) {
    if (s == null) return '';
    return String(s)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

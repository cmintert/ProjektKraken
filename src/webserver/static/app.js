const POLL_INTERVAL_MS = 5000;
let lastUpdate = null;

async function fetchLongform() {
    try {
        const statusEl = document.getElementById('status');
        statusEl.textContent = 'Refreshing...';

        const res = await fetch("/api/longform");
        if (!res.ok) throw new Error(`HTTP ${res.status}`);

        const data = await res.json();
        renderContent(data);
        renderTOC(data.sections);

        statusEl.textContent = 'Live';
        lastUpdate = new Date();
    } catch (err) {
        console.error("Fetch failed", err);
        document.getElementById('status').textContent = 'Offline';
    }
}

function renderContent(data) {
    const container = document.getElementById('longform-content');
    if (!container) return;

    // Naive re-render for MVP. V2 should diff or items.
    // We want to preserve scroll position if possible, but strict replacement is safer for consistency.
    // Let's rely on browser scroll anchoring or simple restore.

    // NOTE: Ideally we would diff the sections. For MVP we just replace innerHTML.
    // However, replacing innerHTML kills scroll and selection. 
    // Let's try to be slightly smarter? No, stick to simple for V1.

    let html = `<h1 class="doc-title">${data.title}</h1>`;

    data.sections.forEach(section => {
        html += `
      <section id="${section.id}" class="longform-item">
        ${section.html}
      </section>
      <hr class="section-divider"/>
    `;
    });

    // Check if content actually changed to avoid unnecessary repaint?
    // We'll trust the polling for now.
    if (container.innerHTML !== html) {
        container.innerHTML = html;
    }
}

function renderTOC(sections) {
    const nav = document.getElementById('toc');
    if (!nav) return;

    // Only re-render if count changed or significantly different?
    // For MVP, just rebuild.
    let html = '';
    sections.forEach(section => {
        html += `<a href="#${section.id}" class="toc-item toc-level-${section.heading_level}">${section.title}</a>`;
    });

    if (nav.innerHTML !== html) {
        nav.innerHTML = html;
    }
}

// Initial Load
document.addEventListener('DOMContentLoaded', () => {
    fetchLongform();

    // Polling
    setInterval(fetchLongform, POLL_INTERVAL_MS);
});

(function () {
    const cfg = window.MAP_CONFIG;

    const typeColors = {
        infrastructure: "#4f46e5",
        ecology: "#16a34a",
        business: "#f59e0b",
        social: "#ec4899",
        transport: "#0ea5e9",
        education: "#8b5cf6",
        culture: "#f43f5e",
    };
    const typeLabels = {
        infrastructure: "Инфраструктура",
        ecology: "Экология",
        business: "Бизнес",
        social: "Социальный",
        transport: "Транспорт",
        education: "Образование",
        culture: "Культура",
    };
    const statusLabels = {
        planned: "Запланирован",
        in_progress: "Реализуется",
        completed: "Завершён",
        paused: "Приостановлен",
    };
    const statusClass = {
        planned: "chip--info",
        in_progress: "chip--warning",
        completed: "chip--success",
        paused: "chip--danger",
    };

    const map = L.map("map", { zoomControl: true }).setView(cfg.center, cfg.zoom);

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution: "&copy; OpenStreetMap",
    }).addTo(map);

    // --- Layers for different display modes ---
    const projectLayer = L.layerGroup();
    const initiativeLayer = L.layerGroup();
    const clusterLayer = (typeof L.markerClusterGroup === "function")
        ? L.markerClusterGroup({ showCoverageOnHover: false, maxClusterRadius: 55 })
        : L.layerGroup();
    let heatLayer = null;

    // Start with markers mode
    projectLayer.addTo(map);
    initiativeLayer.addTo(map);

    const state = {
        type: new Set(),
        status: new Set(),
        district: "",
        q: "",
        layers: { projects: true, initiatives: true },
        mode: "markers", // markers | cluster | heat
        projects: [],
        initiatives: [],
    };

    function projectIcon(type) {
        const color = typeColors[type] || "#4f46e5";
        const html = `<div style="
            width:28px;height:28px;border-radius:50% 50% 50% 0;
            background:${color};
            transform:rotate(-45deg);
            display:flex;align-items:center;justify-content:center;
            border:2px solid #fff;
            box-shadow:0 4px 10px rgba(0,0,0,.2);
        "><div style="transform:rotate(45deg);width:10px;height:10px;border-radius:50%;background:#fff;"></div></div>`;
        return L.divIcon({ html, className: "", iconSize: [28, 28], iconAnchor: [14, 28] });
    }

    function initiativeIcon() {
        const html = `<div style="
            width:26px;height:26px;
            background:#fb923c;
            transform:rotate(45deg);
            border:2px solid #fff;
            box-shadow:0 4px 10px rgba(0,0,0,.2);
            display:flex;align-items:center;justify-content:center;
        "><span style="transform:rotate(-45deg);color:#fff;font-size:12px;font-weight:800;">★</span></div>`;
        return L.divIcon({ html, className: "", iconSize: [26, 26], iconAnchor: [13, 13] });
    }

    function buildProjectPopup(p) {
        const color = typeColors[p.type] || "#4f46e5";
        const safeUrl = /^\//.test(p.url) ? p.url : "/";
        return `
            <div class="popup-title" style="color:${color}">${escHtml(p.title)}</div>
            <div class="popup-meta">${escHtml(typeLabels[p.type] || p.type)} · ${escHtml(statusLabels[p.status] || p.status)}</div>
            <p style="margin:0 0 8px;font-size:13px;">${escHtml(p.short)}</p>
            <a class="popup-link" href="${escHtml(safeUrl)}">Открыть карточку →</a>
        `;
    }

    function buildInitiativePopup(i) {
        const safeUrl = /^\//.test(i.url) ? i.url : "/";
        return `
            <div class="popup-title" style="color:#ea580c">${escHtml(i.title)}</div>
            <div class="popup-meta">Инициатива · собрано ${formatMoney(i.collected)} из ${formatMoney(i.goal)}</div>
            <div class="progress" style="margin:6px 0;"><div class="progress__bar" style="width:${i.progress}%"></div></div>
            <a class="popup-link" href="${escHtml(safeUrl)}">Подробнее →</a>
        `;
    }

    // Compact hover tooltip — title + meta; popup on click still shows full info
    function buildProjectTooltip(p) {
        const color = typeColors[p.type] || "#4f46e5";
        return `<div class="hover-tip">
            <div class="hover-tip__title" style="color:${color}">${escHtml(p.title)}</div>
            <div class="hover-tip__meta">${escHtml(typeLabels[p.type] || p.type)} · ${escHtml(statusLabels[p.status] || p.status)}</div>
            ${p.budget ? `<div class="hover-tip__budget">Бюджет: ${formatMoney(p.budget)}</div>` : ""}
            <div class="hover-tip__hint">Клик — карточка</div>
        </div>`;
    }

    function buildInitiativeTooltip(i) {
        return `<div class="hover-tip">
            <div class="hover-tip__title" style="color:#ea580c">${escHtml(i.title)}</div>
            <div class="hover-tip__meta">Инициатива · ${i.progress}%</div>
            <div class="hover-tip__budget">${formatMoney(i.collected)} из ${formatMoney(i.goal)}</div>
            <div class="hover-tip__hint">Клик — подробности</div>
        </div>`;
    }

    function escHtml(s) {
        return String(s)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");
    }

    function formatMoney(v) {
        if (v === null || v === undefined) return "—";
        return (Number(v).toLocaleString("ru-RU")) + " ₽";
    }

    function buildQuery() {
        const params = new URLSearchParams();
        state.type.forEach(v => params.append("type", v));
        state.status.forEach(v => params.append("status", v));
        if (state.district) params.set("district", state.district);
        if (state.q) params.set("q", state.q);
        return params.toString();
    }

    async function loadProjects() {
        const url = cfg.projectsUrl + "?" + buildQuery();
        const res = await fetch(url);
        const data = await res.json();
        state.projects = data.items;
        refreshMarkers();
        renderResultList();
    }

    async function loadInitiatives() {
        const res = await fetch(cfg.initiativesUrl);
        const data = await res.json();
        state.initiatives = data.items;
        refreshMarkers();
    }

    // Single refresh routine — decides what to render based on current mode
    function refreshMarkers() {
        // Clear everything
        projectLayer.clearLayers();
        initiativeLayer.clearLayers();
        clusterLayer.clearLayers();
        if (heatLayer) { map.removeLayer(heatLayer); heatLayer = null; }

        // Detach layers first, re-attach depending on mode
        if (map.hasLayer(projectLayer)) map.removeLayer(projectLayer);
        if (map.hasLayer(initiativeLayer)) map.removeLayer(initiativeLayer);
        if (map.hasLayer(clusterLayer)) map.removeLayer(clusterLayer);

        if (state.mode === "heat") {
            renderHeatmap();
            return;
        }

        const projectMarkers = [];
        const initiativeMarkers = [];

        if (state.layers.projects) {
            state.projects.forEach(p => {
                const m = L.marker([p.lat, p.lng], { icon: projectIcon(p.type) })
                    .bindPopup(buildProjectPopup(p), { maxWidth: 280 })
                    .bindTooltip(buildProjectTooltip(p), { direction: "top", offset: [0, -24], className: "hover-tip-wrap", sticky: false });
                m._projectId = p.id;
                projectMarkers.push(m);
            });
        }
        if (state.layers.initiatives) {
            state.initiatives.forEach(i => {
                const m = L.marker([i.lat, i.lng], { icon: initiativeIcon() })
                    .bindPopup(buildInitiativePopup(i), { maxWidth: 280 })
                    .bindTooltip(buildInitiativeTooltip(i), { direction: "top", offset: [0, -14], className: "hover-tip-wrap" });
                initiativeMarkers.push(m);
            });
        }

        if (state.mode === "cluster") {
            projectMarkers.forEach(m => clusterLayer.addLayer(m));
            initiativeMarkers.forEach(m => clusterLayer.addLayer(m));
            clusterLayer.addTo(map);
        } else {
            projectMarkers.forEach(m => m.addTo(projectLayer));
            initiativeMarkers.forEach(m => m.addTo(initiativeLayer));
            projectLayer.addTo(map);
            initiativeLayer.addTo(map);
        }
    }

    function renderHeatmap() {
        if (typeof L.heatLayer !== "function") {
            console.warn("Leaflet.heat not loaded");
            return;
        }
        const points = [];
        // Weight projects by budget (log-scaled), initiatives by progress
        if (state.layers.projects) {
            const budgets = state.projects.map(p => p.budget || 0).filter(b => b > 0);
            const maxLog = budgets.length ? Math.log10(Math.max(...budgets)) : 1;
            state.projects.forEach(p => {
                const w = p.budget ? Math.log10(p.budget) / maxLog : 0.4;
                points.push([p.lat, p.lng, Math.max(0.3, w)]);
            });
        }
        if (state.layers.initiatives) {
            state.initiatives.forEach(i => {
                points.push([i.lat, i.lng, 0.4 + (i.progress || 0) / 200]);
            });
        }
        heatLayer = L.heatLayer(points, {
            radius: 40,
            blur: 28,
            maxZoom: 13,
            gradient: { 0.2: "#4f46e5", 0.5: "#16a34a", 0.8: "#f59e0b", 1.0: "#f43f5e" },
        }).addTo(map);
    }

    function renderResultList() {
        const list = document.getElementById("resultList");
        const count = document.getElementById("resultCount");
        count.textContent = state.projects.length;
        if (!state.projects.length) {
            list.innerHTML = '<div class="empty-state">Ничего не найдено.<br>Попробуйте изменить фильтры.</div>';
            return;
        }
        list.innerHTML = state.projects.slice(0, 30).map(p => `
            <div class="result-card" data-id="${p.id}" data-lat="${p.lat}" data-lng="${p.lng}">
                <div class="result-card__title">${escHtml(p.title)}</div>
                <div class="result-card__meta">
                    <span class="chip chip--primary">${escHtml(typeLabels[p.type] || p.type)}</span>
                    <span class="chip ${statusClass[p.status] || ''}">${escHtml(statusLabels[p.status] || p.status)}</span>
                    <span>${escHtml(p.district)}</span>
                </div>
            </div>
        `).join("");
        list.querySelectorAll(".result-card").forEach(el => {
            el.addEventListener("click", () => {
                const lat = parseFloat(el.dataset.lat);
                const lng = parseFloat(el.dataset.lng);
                const id = parseInt(el.dataset.id, 10);
                map.flyTo([lat, lng], 14, { duration: 0.7 });
                const openIfMatches = (m) => { if (m._projectId === id) m.openPopup(); };
                projectLayer.eachLayer(openIfMatches);
                if (state.mode === "cluster") clusterLayer.eachLayer(openIfMatches);
            });
        });
    }

    // ---- filters wiring ----
    document.querySelectorAll('.filter-pills[data-filter="type"] .filter-pill').forEach(btn => {
        btn.addEventListener("click", () => {
            btn.classList.toggle("active");
            const val = btn.dataset.value;
            if (state.type.has(val)) state.type.delete(val);
            else state.type.add(val);
            loadProjects();
        });
    });
    document.querySelectorAll('.filter-pills[data-filter="status"] .filter-pill').forEach(btn => {
        btn.addEventListener("click", () => {
            btn.classList.toggle("active");
            const val = btn.dataset.value;
            if (state.status.has(val)) state.status.delete(val);
            else state.status.add(val);
            loadProjects();
        });
    });
    document.querySelectorAll('.filter-pills[data-filter="layer"] .filter-pill').forEach(btn => {
        btn.addEventListener("click", () => {
            btn.classList.toggle("active");
            const val = btn.dataset.value;
            state.layers[val] = btn.classList.contains("active");
            refreshMarkers();
        });
    });
    // Mode switcher — exclusive selection
    document.querySelectorAll('.filter-pills[data-filter="mode"] .filter-pill').forEach(btn => {
        btn.addEventListener("click", () => {
            document.querySelectorAll('.filter-pills[data-filter="mode"] .filter-pill').forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            state.mode = btn.dataset.value;
            refreshMarkers();
        });
    });

    document.getElementById("districtSelect").addEventListener("change", e => {
        state.district = e.target.value;
        loadProjects();
    });

    let searchTimer = null;
    document.getElementById("searchInput").addEventListener("input", e => {
        clearTimeout(searchTimer);
        searchTimer = setTimeout(() => {
            state.q = e.target.value.trim();
            loadProjects();
        }, 250);
    });

    document.getElementById("resetFilters").addEventListener("click", () => {
        state.type.clear(); state.status.clear(); state.district = ""; state.q = "";
        document.querySelectorAll('.filter-pills[data-filter="type"] .filter-pill, .filter-pills[data-filter="status"] .filter-pill').forEach(b => b.classList.remove("active"));
        document.getElementById("districtSelect").value = "";
        document.getElementById("searchInput").value = "";
        loadProjects();
    });

    // --- Administrative Boundaries ---
    let boundaryLayers = [];
    let boundariesVisible = false;

    function toggleBoundaries() {
        const btn = document.getElementById("toggleBoundaries");
        if (!btn) return;
        if (boundariesVisible) {
            boundaryLayers.forEach(l => map.removeLayer(l));
            boundaryLayers = [];
            boundariesVisible = false;
            btn.classList.remove("active");
            btn.textContent = "Показать";
        } else {
            (window.DISTRICT_BOUNDARIES || []).forEach(d => {
                const polygon = L.polygon(d.coords, {
                    color: d.color,
                    weight: 2,
                    fillColor: d.color,
                    fillOpacity: 0.07,
                    dashArray: "6 4",
                }).addTo(map);
                polygon.bindTooltip(d.name, { permanent: true, direction: "center", className: "boundary-label" });
                boundaryLayers.push(polygon);
            });
            boundariesVisible = true;
            btn.classList.add("active");
            btn.textContent = "Скрыть";
        }
    }

    const toggleBtn = document.getElementById("toggleBoundaries");
    if (toggleBtn) toggleBtn.addEventListener("click", toggleBoundaries);

    // Initial load
    loadProjects();
    loadInitiatives();
})();

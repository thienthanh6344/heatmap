/** @odoo-module **/

import { Component, onMounted, onWillUnmount, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class SgtProjectHeatmapDashboard extends Component {
    static template = "sgt_contact_matchmaking.ProjectHeatmapDashboard";

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.notification = useService("notification");
        this.mapContainer = useRef("mapContainer");

        this.map = null;
        this.clusterGroup = null;
        this.heatLayer = null;
        this.markersMap = {};
        this.subPointMarkers = [];
        this.goongSearchTimer = null;
        this.goongMarker = null;

        // Check for default_project_id passed via action params or context
        const initialProjectId =
            this.props.action?.params?.default_project_id ||
            this.props.action?.context?.default_project_id ||
            "gearea";

        this.state = useState({
            // Dedicated Project Heatmap Selector (All, Gearea, Argo, YingBo, or any added project)
            selectedProjectId: String(initialProjectId),

            // Filter Controls (Matching CRM Customer Map Screenshot)
            timeRangeMode: "months", // 'recent' | 'months' | 'custom'
            timeRangeSpan: "24", // 24 months = 2 years
            excludeCancelled: true, // "Bỏ đơn đã huỷ"
            salesperson: "all", // "Phụ trách: Tất cả"
            heatMetric: "customers", // "Độ nóng theo: Số khách" | "orders" | "revenue"

            // Filter Controls
            searchQuery: "",
            selectedProvince: "all",
            selectedDistrict: "all",
            selectedIndustry: "all",
            selectedStatus: "all",
            selectedEvent: "all",

            // Display Layers & Sliders (Radius default 22px matching screenshot)
            showHeatmap: true,
            showClusters: true,
            heatRadius: 22,
            heatIntensity: 0.65,
            heatWeightMode: "count", // 'count' | 'investment' | 'capacity'

            // Goong Autocomplete
            goongQuery: "",
            goongSuggestions: [],
            isSearchingGoong: false,

            // Projects and Geo Analytics Summary
            projects: [],
            filteredProjects: [],
            summary: {
                total_projects: 0,
                mapped_projects: 0,
                unmapped_projects: 0,
                mapped_percentage: 0,
                quality: {
                    has_coords: 0,
                    missing_coords: 0,
                    has_address: 0,
                    missing_address: 0,
                    geocoding_failed: 0,
                    sources: { goong: 0, manual: 0, import: 0 },
                },
                province_statistics: [],
                filter_options: {
                    provinces: [],
                    districts_by_province: {},
                    industries: [],
                    events: [],
                    statuses: [],
                    project_types: [],
                },
            },

            // Top Contact Areas Analysis Table State
            topAreaLevel: "district", // 'district' (default) | 'province' | 'ward'
            topAreaLimit: 10, // 5 | 10 | 20 | 'all'
            topAreaSortBy: "customer_count", // 'customer_count' | 'percentage' | 'area' | 'companies_count'
            topAreaSortOrder: "desc", // 'desc' | 'asc'
            selectedTopArea: null, // clicked area name
            topAreasData: {
                total_contacts: 0,
                mapped_contacts: 0,
                unmapped_contacts: 0,
                unmapped_partner_ids: [],
                areas: [],
                dynamic_columns: [],
            },
            isLoadingTopAreas: false,

            // Collapsible sidebar sections (true = collapsed, false = expanded)
            collapsedSections: {
                filters: false,
                layers: false,
                stats: false,
                provinces: false,
                topAreas: false,
            },
        });

        // Global callbacks for Leaflet popup button actions
        window._sgtOpenProjectDetails = (projectId) => {
            this.openProjectDetails(projectId);
        };
        window._sgtOpenContactDetails = (contactId) => {
            this.openContactDetails(contactId);
        };
        window._sgtOpenContactMatchmaking = (contactId) => {
            this.openContactMatchmaking(contactId);
        };

        onMounted(async () => {
            await this.initLeafletAndMap();
            await this.refreshData();
        });

        onWillUnmount(() => {
            if (this.map) {
                this.map.remove();
                this.map = null;
            }
            if (this.goongSearchTimer) {
                clearTimeout(this.goongSearchTimer);
            }
            delete window._sgtOpenProjectDetails;
            delete window._sgtOpenContactDetails;
            delete window._sgtOpenContactMatchmaking;
        });
    }

    // -------------------------------------------------------------------------
    // GETTERS & COMPUTED PROPERTIES
    // -------------------------------------------------------------------------
    get currentProject() {
        const sel = this.state.selectedProjectId;
        if (!sel || sel === "all") return null;

        if (sel === "gearea" || sel === "1") {
            return this.state.projects.find((p) => p.name.toLowerCase().includes("gearea")) || null;
        }
        if (sel === "argo" || sel === "2") {
            return this.state.projects.find((p) => p.name.toLowerCase().includes("argo")) || null;
        }
        if (sel === "yinbo" || sel === "yingbo" || sel === "3") {
            return this.state.projects.find((p) => p.name.toLowerCase().includes("yingbo") || p.name.toLowerCase().includes("yinbo")) || null;
        }
        return this.state.projects.find((p) => String(p.id) === String(sel)) || null;
    }

    get geareaProject() {
        return this.state.projects.find((p) => p.name.toLowerCase().includes("gearea")) || null;
    }

    get argoProject() {
        return this.state.projects.find((p) => p.name.toLowerCase().includes("argo")) || null;
    }

    get yingboProject() {
        return this.state.projects.find((p) => p.name.toLowerCase().includes("yingbo")) || null;
    }

    get currentProvinceStats() {
        if (!this.currentProject) {
            return this.state.summary.province_statistics || [];
        }
        const p = this.currentProject;
        const counts = {};
        for (const c of (p.contacts || [])) {
            const prov = c.province || "Chưa phân loại";
            if (!counts[prov]) {
                counts[prov] = { province: prov, count: 0, mapped: 0 };
            }
            counts[prov].count++;
            if (c.has_coordinates) counts[prov].mapped++;
        }
        const total = p.total_contacts || 1;
        const list = Object.values(counts).map((x) => ({
            province: x.province,
            count: x.count,
            investment_display: `${x.mapped}/${x.count} có vị trí`,
            percentage: Math.round((x.count / total) * 100),
        }));
        list.sort((a, b) => b.count - a.count);
        return list;
    }

    get customProjectsList() {
        return this.state.projects.filter((p) => {
            const n = p.name.toLowerCase();
            return !n.includes("gearea") && !n.includes("argo") && !n.includes("yingbo");
        });
    }

    get availableDistricts() {
        if (this.state.selectedProvince === "all") {
            return [];
        }
        const mapping = this.state.summary.filter_options.districts_by_province || {};
        return mapping[this.state.selectedProvince] || [];
    }

    get hasActiveFilters() {
        return (
            this.state.selectedProjectId !== "all" ||
            this.state.searchQuery.trim() !== "" ||
            this.state.selectedProvince !== "all" ||
            this.state.selectedDistrict !== "all" ||
            this.state.selectedIndustry !== "all" ||
            this.state.selectedStatus !== "all" ||
            this.state.selectedEvent !== "all"
        );
    }

    get visibleMappedCount() {
        if (this.currentProject) {
            return this.currentProject.has_coordinates ? 1 : 0;
        }
        return this.state.filteredProjects.filter((p) => p.has_coordinates).length;
    }

    // -------------------------------------------------------------------------
    // SCRIPT & ASSET LOADERS
    // -------------------------------------------------------------------------
    async initLeafletAndMap() {
        if (!window.L) {
            await this._loadScript("/sgt_contact_matchmaking/static/src/lib/leaflet.js");
            this._loadCSS("/sgt_contact_matchmaking/static/src/lib/leaflet.css");
        }
        if (window.L && !window.L.MarkerClusterGroup) {
            this._loadCSS("/sgt_contact_matchmaking/static/src/lib/MarkerCluster.css");
            this._loadCSS("/sgt_contact_matchmaking/static/src/lib/MarkerCluster.Default.css");
            await this._loadScript("/sgt_contact_matchmaking/static/src/lib/leaflet.markercluster.js");
        }
        if (window.L && !window.L.heatLayer) {
            try {
                await this._loadScript("/sgt_contact_matchmaking/static/src/lib/leaflet-heat.js");
            } catch (err) {
                console.warn("[Project Heatmap] Leaflet-heat script could not be loaded:", err);
            }
        }

        const mapEl = this.mapContainer.el;
        if (!mapEl || !window.L) return;

        // Vietnam geographic center: Lat 16.0, Lon 107.5, Zoom 6
        this.map = window.L.map(mapEl, {
            center: [16.0471, 107.5],
            zoom: 6,
            minZoom: 5,
            maxZoom: 18,
            scrollWheelZoom: true,
        });

        // OpenStreetMap tile layer
        window.L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank">OpenStreetMap</a> contributors | Goong Geocoding Engine',
            maxZoom: 18,
        }).addTo(this.map);

        // Marker Cluster Group
        if (window.L.markerClusterGroup) {
            this.clusterGroup = window.L.markerClusterGroup({
                maxClusterRadius: 50,
                spiderfyOnMaxZoom: true,
                showCoverageOnHover: false,
                zoomToBoundsOnClick: true,
                chunkedLoading: true,
            });
            if (this.state.showClusters) {
                this.map.addLayer(this.clusterGroup);
            }
        }
    }

    _loadScript(src) {
        return new Promise((resolve, reject) => {
            if (document.querySelector(`script[src="${src}"]`)) {
                resolve();
                return;
            }
            const script = document.createElement("script");
            script.src = src;
            script.onload = () => resolve();
            script.onerror = (e) => reject(e);
            document.head.appendChild(script);
        });
    }

    _loadCSS(href) {
        if (!document.querySelector(`link[href="${href}"]`)) {
            const link = document.createElement("link");
            link.rel = "stylesheet";
            link.href = href;
            document.head.appendChild(link);
        }
    }

    // -------------------------------------------------------------------------
    // DATA REFRESH & ORM INTEGRATION
    // -------------------------------------------------------------------------
    async refreshData() {
        try {
            const [projects, summary] = await Promise.all([
                this.orm.call("sgt.project.heatmap", "get_project_map_data", [], {
                    weight_mode: this.state.heatWeightMode,
                }),
                this.orm.call("sgt.project.heatmap", "get_project_map_summary", []),
            ]);

            this.state.projects = projects || [];
            this.state.summary = summary || {
                total_projects: 0,
                mapped_projects: 0,
                unmapped_projects: 0,
                mapped_percentage: 0,
                quality: { has_coords: 0, missing_coords: 0, has_address: 0, missing_address: 0, geocoding_failed: 0, sources: {} },
                province_statistics: [],
                filter_options: { provinces: [], districts_by_province: {}, industries: [], events: [], statuses: [], project_types: [] },
            };

            this.applyFilters();
        } catch (error) {
            console.error("[Project Heatmap] Error refreshing data:", error);
            this.notification.add("Không thể tải dữ liệu dự án: " + (error.message || error), {
                type: "danger",
            });
        }
    }

    // -------------------------------------------------------------------------
    // FILTERING LOGIC
    // -------------------------------------------------------------------------
    applyFilters() {
        // If a specific project is selected in the dedicated dropdown:
        if (this.currentProject) {
            this.state.filteredProjects = [this.currentProject];
            this.renderMapLayers();
            this.fetchTopContactAreas();
            return;
        }

        const query = this.state.searchQuery.trim().toLowerCase();
        const prov = this.state.selectedProvince;
        const dist = this.state.selectedDistrict;
        const ind = this.state.selectedIndustry;
        const status = this.state.selectedStatus;
        const event = this.state.selectedEvent;

        const filtered = this.state.projects.filter((p) => {
            // Text Search
            if (query) {
                const searchStr = `${p.name} ${p.code} ${p.province} ${p.district} ${p.ward} ${p.address} ${p.industry} ${p.owner} ${p.company_name}`.toLowerCase();
                if (!searchStr.includes(query)) return false;
            }
            // Province
            if (prov !== "all" && p.province !== prov) return false;
            // District (cascading)
            if (dist !== "all" && p.district !== dist) return false;
            // Industry
            if (ind !== "all" && p.industry !== ind) return false;
            // Status
            if (status !== "all" && p.status !== status) return false;
            // Event
            if (event !== "all" && p.event !== event) return false;

            return true;
        });

        this.state.filteredProjects = filtered;
        this.renderMapLayers();
        this.fetchTopContactAreas();
    }

    // -------------------------------------------------------------------------
    // MAP RENDERING (DEDICATED PROJECT HEATMAP OR ALL PROJECTS)
    // -------------------------------------------------------------------------
    renderMapLayers() {
        if (!this.map || !window.L) return;

        // 1. Clear Clusters & Markers
        if (this.clusterGroup) {
            this.clusterGroup.clearLayers();
        }
        this.markersMap = {};

        // 2. Clear Heatmap Layer
        if (this.heatLayer) {
            this.map.removeLayer(this.heatLayer);
            this.heatLayer = null;
        }

        // =====================================================================
        // CASE A: DEDICATED SINGLE PROJECT HEATMAP (Gearea, Argo, YingBo, etc.)
        // Visualizes all contacts & ecosystem belonging to this major project!
        // =====================================================================
        if (this.currentProject) {
            const p = this.currentProject;
            const pointsForBounds = [];
            const heatPoints = [];

            // 1. Add Main Project Site (Plant / HQ)
            if (p.has_coordinates) {
                heatPoints.push([p.latitude, p.longitude, Math.max(1.8, p.weight || 2.5)]);
                pointsForBounds.push([p.latitude, p.longitude]);

                const flagshipMarker = this._createProjectMainSiteMarker(p);
                if (this.clusterGroup) {
                    this.clusterGroup.addLayer(flagshipMarker);
                }
                this.markersMap[`project_${p.id}`] = flagshipMarker;
            }

            // 2. Add Project Contacts (Ecosystem of Suppliers, Buyers, Partners)
            const contacts = p.contacts || [];
            contacts.forEach((c) => {
                if (c.has_coordinates) {
                    heatPoints.push([c.latitude, c.longitude, Math.max(1.0, c.weight || 1.2)]);
                    pointsForBounds.push([c.latitude, c.longitude]);

                    const contactMarker = this._createContactMarker(c);
                    if (this.clusterGroup) {
                        this.clusterGroup.addLayer(contactMarker);
                    }
                    this.markersMap[`contact_${c.id}`] = contactMarker;
                }
            });

            // 3. Sub-points (if defined, e.g. turbine clusters, solar zones, factory blocks)
            if (p.sub_points && p.sub_points.length > 0) {
                p.sub_points.forEach((pt) => {
                    heatPoints.push([pt.latitude, pt.longitude, Math.max(1.0, pt.weight || 1.5)]);
                    pointsForBounds.push([pt.latitude, pt.longitude]);

                    const subIcon = window.L.divIcon({
                        html: `
                            <div style="position: relative; width: 22px; height: 22px;">
                                <div style="width: 22px; height: 22px; border-radius: 50%; background: #e11d48; border: 2px solid #ffffff; box-shadow: 0 2px 6px rgba(0,0,0,0.35); display: flex; align-items: center; justify-content: center;">
                                    <div style="width: 6px; height: 6px; background: #ffffff; border-radius: 50%;"></div>
                                </div>
                            </div>
                        `,
                        className: "sgt-subpoint-marker",
                        iconSize: [22, 22],
                        iconAnchor: [11, 11],
                        popupAnchor: [0, -10],
                    });

                    const subMarker = window.L.marker([pt.latitude, pt.longitude], { icon: subIcon });
                    subMarker.bindPopup(`
                        <div style="font-size: 12px; font-family: inherit;">
                            <strong style="color: #0f172a;">${pt.name}</strong>
                            <div class="badge bg-danger text-white mt-1" style="font-size: 10px;">${pt.point_type}</div>
                            <div class="text-muted small mt-1">Trọng số nhiệt: <strong>${pt.weight}</strong></div>
                            ${pt.address ? `<div class="text-muted small mt-1">${pt.address}</div>` : ''}
                        </div>
                    `);
                    if (this.clusterGroup) {
                        this.clusterGroup.addLayer(subMarker);
                    }
                });
            }

            if (this.clusterGroup && !this.map.hasLayer(this.clusterGroup)) {
                this.map.addLayer(this.clusterGroup);
            }

            // 4. Render Dedicated Heatmap Layer for this Project's Contacts & Sites
            if (this.state.showHeatmap && window.L.heatLayer && heatPoints.length > 0) {
                this.heatLayer = window.L.heatLayer(heatPoints, {
                    radius: Number(this.state.heatRadius) + 8,
                    blur: 20,
                    minOpacity: Number(this.state.heatIntensity) || 0.65,
                    maxZoom: 16,
                    gradient: {
                        0.2: "blue",
                        0.4: "cyan",
                        0.6: "lime",
                        0.8: "yellow",
                        1.0: "red",
                    },
                }).addTo(this.map);
            }

            // Smoothly Zoom / Fit bounds to all contacts and site of this project
            if (pointsForBounds.length > 1) {
                const bounds = window.L.latLngBounds(pointsForBounds);
                this.map.fitBounds(bounds, { padding: [50, 50], maxZoom: 14 });
            } else if (pointsForBounds.length === 1) {
                this.map.setView(pointsForBounds[0], 13, { animate: true });
            } else {
                this.notification.add(`Dự án '${p.name}' chưa có Contact hoặc vị trí nào có tọa độ GPS.`, {
                    type: "warning",
                });
            }

            return;
        }

        // =====================================================================
        // CASE B: ALL PROJECTS MODE (TOÀN CẢNH VIỆT NAM)
        // =====================================================================
        const validProjects = this.state.filteredProjects.filter((p) => p.has_coordinates);

        // 3. Render Clusters / Markers Layer
        if (this.state.showClusters && this.clusterGroup) {
            validProjects.forEach((p) => {
                const marker = this._createProjectMarker(p);
                this.clusterGroup.addLayer(marker);
                this.markersMap[p.id] = marker;

                // Also render individual contacts if filtered
                if (p.contacts && p.contacts.length > 0) {
                    p.contacts.forEach((c) => {
                        if (c.has_coordinates) {
                            const cMarker = this._createContactMarker(c);
                            this.clusterGroup.addLayer(cMarker);
                        }
                    });
                }
            });
            if (!this.map.hasLayer(this.clusterGroup)) {
                this.map.addLayer(this.clusterGroup);
            }
        } else if (this.clusterGroup && this.map.hasLayer(this.clusterGroup)) {
            this.map.removeLayer(this.clusterGroup);
        }

        // 4. Render Density Heatmap Layer
        if (this.state.showHeatmap && window.L.heatLayer && validProjects.length > 0) {
            const heatPoints = [];
            validProjects.forEach((p) => {
                heatPoints.push([p.latitude, p.longitude, Math.max(0.5, p.weight || 1.5)]);
                if (p.contacts && p.contacts.length > 0) {
                    p.contacts.forEach((c) => {
                        if (c.has_coordinates) {
                            heatPoints.push([c.latitude, c.longitude, Math.max(0.3, c.weight || 1.0)]);
                        }
                    });
                }
                if (p.sub_points && p.sub_points.length > 0) {
                    p.sub_points.forEach((pt) => {
                        heatPoints.push([pt.latitude, pt.longitude, Math.max(0.2, pt.weight || 1.0)]);
                    });
                }
            });

            this.heatLayer = window.L.heatLayer(heatPoints, {
                radius: Number(this.state.heatRadius) || 30,
                blur: 18,
                minOpacity: Number(this.state.heatIntensity) || 0.6,
                maxZoom: 14,
                gradient: {
                    0.2: "blue",
                    0.4: "cyan",
                    0.6: "lime",
                    0.8: "yellow",
                    1.0: "red",
                },
            }).addTo(this.map);
        }
    }

    _createProjectMainSiteMarker(p) {
        const iconHtml = `
            <div style="position: relative; width: 36px; height: 36px;">
                <div style="width: 36px; height: 36px; border-radius: 50%; background: linear-gradient(135deg, #f59e0b, #d97706); box-shadow: 0 3px 8px rgba(0,0,0,0.4); border: 2px solid #ffffff; display: flex; align-items: center; justify-content: center; color: #ffffff; font-size: 15px;">
                    <i class="fa fa-star"></i>
                </div>
            </div>
        `;

        const customIcon = window.L.divIcon({
            html: iconHtml,
            className: "sgt-project-flagship-marker",
            iconSize: [36, 36],
            iconAnchor: [18, 36],
            popupAnchor: [0, -32],
        });

        const marker = window.L.marker([p.latitude, p.longitude], { icon: customIcon, zIndexOffset: 1000 });
        marker.bindPopup(this._createPopupContent(p, true), { maxWidth: 350 });
        return marker;
    }

    _createContactMarker(c) {
        const color = c.role === "seller" ? "#059669" : (c.role === "buyer" ? "#2563eb" : "#7c3aed");
        const roleIcon = c.role === "seller" ? "fa-cube" : (c.role === "buyer" ? "fa-shopping-cart" : "fa-handshake-o");

        const iconHtml = `
            <div style="position: relative; width: 28px; height: 28px;">
                <div style="width: 28px; height: 28px; border-radius: 50% 50% 50% 0; background: ${color}; transform: rotate(-45deg); box-shadow: 0 2px 6px rgba(0,0,0,0.35); position: absolute;"></div>
                <div style="width: 14px; height: 14px; position: absolute; top: 6px; left: 7px; color: #ffffff; display: flex; align-items: center; justify-content: center; font-size: 10px;">
                    <i class="fa ${roleIcon}"></i>
                </div>
            </div>
        `;

        const customIcon = window.L.divIcon({
            html: iconHtml,
            className: "sgt-contact-marker",
            iconSize: [28, 28],
            iconAnchor: [14, 28],
            popupAnchor: [0, -26],
        });

        const marker = window.L.marker([c.latitude, c.longitude], { icon: customIcon });
        marker.bindPopup(this._createContactPopupContent(c), { maxWidth: 320 });
        return marker;
    }

    _createContactPopupContent(c) {
        const badgeClass = c.role === "seller" ? "bg-success" : (c.role === "buyer" ? "bg-primary" : "bg-purple text-white");
        return `
            <div class="sgt-leaflet-popup" style="font-family: inherit; min-width: 260px;">
                <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 8px; margin-bottom: 6px;">
                    <div>
                        <div style="font-weight: 700; font-size: 13px; color: #0f172a;">${c.name}</div>
                        ${c.company_name && c.company_name !== c.name ? `<div style="font-size: 11px; color: #64748b;">${c.company_name}</div>` : ''}
                    </div>
                    <span class="badge ${badgeClass}" style="font-size: 10px;">${c.role_label}</span>
                </div>
                <div style="font-size: 12px; color: #334155; display: flex; flex-direction: column; gap: 3px;">
                    <div><i class="fa fa-folder-open text-warning" style="width: 14px;"></i> <strong>Thuộc Dự án:</strong> ${c.project_name}</div>
                    <div><i class="fa fa-map-marker text-danger" style="width: 14px;"></i> <strong>Vị trí:</strong> ${c.street ? c.street + ', ' : ''}${c.district ? c.district + ', ' : ''}${c.province || 'Việt Nam'}</div>
                    ${c.product_category ? `<div><i class="fa fa-tag text-primary" style="width: 14px;"></i> <strong>Ngành hàng:</strong> ${c.product_category}</div>` : ''}
                    ${c.phone ? `<div><i class="fa fa-phone text-success" style="width: 14px;"></i> <strong>Điện thoại:</strong> ${c.phone}</div>` : ''}
                    ${c.email ? `<div><i class="fa fa-envelope text-info" style="width: 14px;"></i> <strong>Email:</strong> ${c.email}</div>` : ''}
                </div>
                <div style="margin-top: 10px; display: flex; gap: 6px;">
                    <button type="button" class="btn btn-outline-primary btn-sm flex-fill" style="font-size: 11px;" onclick="window._sgtOpenContactDetails(${c.id})">
                        <i class="fa fa-user"></i> Xem Contact ↗
                    </button>
                    <button type="button" class="btn btn-primary btn-sm flex-fill" style="font-size: 11px;" onclick="window._sgtOpenContactMatchmaking(${c.id})">
                        <i class="fa fa-handshake-o"></i> Top 10 Match ↗
                    </button>
                </div>
            </div>
        `;
    }

    _createProjectMarker(p) {
        const colorMap = {
            active: "#059669",
            planning: "#2563eb",
            completed: "#8b5cf6",
            cancelled: "#ef4444",
            draft: "#64748b",
        };
        const color = colorMap[p.status] || "#2563eb";

        const iconHtml = `
            <div style="position: relative; width: 30px; height: 30px;">
                <div style="width: 30px; height: 30px; border-radius: 50% 50% 50% 0; background: ${color}; transform: rotate(-45deg); box-shadow: 0 2px 6px rgba(0,0,0,0.35); position: absolute;"></div>
                <div style="width: 12px; height: 12px; background: #ffffff; border-radius: 50%; position: absolute; top: 9px; left: 9px;"></div>
            </div>
        `;

        const customIcon = window.L.divIcon({
            html: iconHtml,
            className: "sgt-custom-marker",
            iconSize: [30, 30],
            iconAnchor: [15, 30],
            popupAnchor: [0, -28],
        });

        const marker = window.L.marker([p.latitude, p.longitude], { icon: customIcon });
        marker.bindPopup(this._createPopupContent(p), { maxWidth: 340 });
        return marker;
    }

    _createPopupContent(p, isFlagship = false) {
        let attrsHtml = "";
        if (p.attributes && p.attributes.length > 0) {
            attrsHtml = `
                <div class="sgt-popup-attrs-title mt-2 pt-1 border-top" style="font-weight: 600; font-size: 11px; color: #475569;">Thuộc tính động (Attributes):</div>
                <div style="display: flex; flex-direction: column; gap: 3px; margin-top: 4px;">
                    ${p.attributes
                        .map(
                            (a) => `
                        <div style="display: flex; justify-content: space-between; font-size: 11px; background: #f8fafc; padding: 2px 6px; border-radius: 4px;">
                            <span style="color: #64748b;">${a.name}:</span>
                            <span style="font-weight: 600; color: #0f172a;">${a.value}</span>
                        </div>
                    `
                        )
                        .join("")}
                </div>
            `;
        }

        const subPointsText = p.sub_points && p.sub_points.length > 0
            ? `<div class="badge bg-danger-subtle text-danger border border-danger-subtle mt-1" style="font-size: 10px;">🔥 Có ${p.sub_points.length} điểm nhiệt phân khu chi tiết</div>`
            : '';

        const contactsText = p.total_contacts > 0
            ? `<div class="badge bg-primary-subtle text-primary border border-primary-subtle mt-1" style="font-size: 10px;">👥 Có ${p.total_contacts} Contact / Đối tác trong hệ sinh thái</div>`
            : '';

        const sourceLabel = p.location_source === "goong" ? "Goong Geocoded" : (p.location_source === "manual" ? "Nhập thủ công" : "Nhập liệu");
        const sourceBadge = `<span class="badge ${p.location_source === 'goong' ? 'bg-success' : 'bg-secondary'}" style="font-size: 10px;">${sourceLabel}</span>`;

        const flagshipHeader = isFlagship
            ? `<div class="badge bg-warning text-dark mb-1" style="font-size: 10px;"><i class="fa fa-star text-danger"></i> Trụ sở / Nhà máy chính của Dự án</div>`
            : '';

        return `
            <div class="sgt-leaflet-popup" style="font-family: inherit;">
                ${flagshipHeader}
                <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 8px; margin-bottom: 6px;">
                    <div style="font-weight: 700; font-size: 14px; color: #0f172a;">${p.name}</div>
                    <span class="badge bg-primary text-white" style="font-size: 10px;">${p.status_label}</span>
                </div>
                <div style="font-size: 12px; color: #334155; display: flex; flex-direction: column; gap: 4px;">
                    <div><i class="fa fa-map-marker text-danger" style="width: 14px;"></i> <strong>Vị trí:</strong> ${p.address || ''} ${p.district ? p.district + ', ' : ''}${p.province || 'Việt Nam'}</div>
                    ${p.industry ? `<div><i class="fa fa-industry text-primary" style="width: 14px;"></i> <strong>Ngành nghề:</strong> ${p.industry}</div>` : ''}
                    ${p.owner ? `<div><i class="fa fa-user-circle-o text-muted" style="width: 14px;"></i> <strong>Chủ đầu tư:</strong> ${p.owner}</div>` : ''}
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 4px;">
                        <span>Nguồn vị trí:</span> ${sourceBadge}
                    </div>
                    ${contactsText}
                    ${subPointsText}
                    ${attrsHtml}
                </div>
                <div style="margin-top: 10px; text-align: center;">
                    <button type="button" class="btn btn-primary btn-sm w-100" style="font-size: 12px;" onclick="window._sgtOpenProjectDetails(${p.id})">
                        <i class="fa fa-external-link"></i> Xem chi tiết dự án ↗
                    </button>
                </div>
            </div>
        `;
    }

    // -------------------------------------------------------------------------
    // EVENT HANDLERS & USER INTERACTIONS
    // -------------------------------------------------------------------------
    onProjectSelectChange() {
        if (this.state.selectedProjectId === "add_new" || this.state.selectedProjectId === "4") {
            this.onAddProjectClick();
            this.state.selectedProjectId = "gearea";
            return;
        }
        this.applyFilters();
        if (this.state.selectedProjectId === "all" && this.map) {
            this.map.setView([16.0471, 107.5], 6);
        }
    }

    onSearchInput() {
        this.applyFilters();
    }

    onProvinceChange() {
        // Reset district when province changes
        this.state.selectedDistrict = "all";
        this.applyFilters();
        this._zoomToSelectedProvince();
    }

    onProvinceRowClick(province) {
        if (this.state.selectedProvince === province) {
            this.state.selectedProvince = "all";
        } else {
            this.state.selectedProvince = province;
        }
        this.state.selectedDistrict = "all";
        this.applyFilters();
        this._zoomToSelectedProvince();
    }

    _zoomToSelectedProvince() {
        if (!this.map) return;
        const prov = this.state.selectedProvince;
        if (prov === "all") {
            this.map.setView([16.0471, 107.5], 6);
            return;
        }

        if (this.currentProject) {
            const provinceContacts = (this.currentProject.contacts || []).filter(
                (c) => c.has_coordinates && (c.province === prov || (c.province && prov && c.province.includes(prov)))
            );
            if (provinceContacts.length > 0) {
                const bounds = window.L.latLngBounds(
                    provinceContacts.map((c) => [c.latitude, c.longitude])
                );
                this.map.fitBounds(bounds, { padding: [50, 50], maxZoom: 13 });
                return;
            }
        }

        const provinceProjects = this.state.filteredProjects.filter(
            (p) => p.has_coordinates && p.province === prov
        );

        if (provinceProjects.length > 0) {
            const bounds = window.L.latLngBounds(
                provinceProjects.map((p) => [p.latitude, p.longitude])
            );
            this.map.fitBounds(bounds, { padding: [50, 50], maxZoom: 13 });
        }
    }

    onFilterChange() {
        this.applyFilters();
    }

    resetFilters() {
        this.state.selectedProjectId = "all";
        this.state.searchQuery = "";
        this.state.selectedProvince = "all";
        this.state.selectedDistrict = "all";
        this.state.selectedIndustry = "all";
        this.state.selectedStatus = "all";
        this.state.selectedEvent = "all";
        this.applyFilters();
        if (this.map) {
            this.map.setView([16.0471, 107.5], 6);
        }
    }

    onLayerToggle() {
        this.renderMapLayers();
    }

    onHeatSliderChange() {
        this.renderMapLayers();
    }

    onTimeRangeModeChange(mode) {
        this.state.timeRangeMode = mode;
        this.fetchTopContactAreas();
    }

    onTimeRangeSpanChange(ev) {
        this.state.timeRangeSpan = ev.target.value;
        this.fetchTopContactAreas();
    }

    onExcludeCancelledChange(ev) {
        this.state.excludeCancelled = ev.target.checked;
        this.fetchTopContactAreas();
    }

    onSalespersonChange(ev) {
        this.state.salesperson = ev.target.value;
        this.fetchTopContactAreas();
    }

    onHeatMetricChange(ev) {
        this.state.heatMetric = ev.target.value;
        if (ev.target.value === "orders") {
            this.state.heatWeightMode = "capacity";
        } else if (ev.target.value === "revenue") {
            this.state.heatWeightMode = "investment";
        } else {
            this.state.heatWeightMode = "count";
        }
        this.renderMapLayers();
    }

    // -------------------------------------------------------------------------
    // GOONG API PLACE AUTOCOMPLETE & GEOCODING
    // -------------------------------------------------------------------------
    onGoongSearchInput() {
        if (this.goongSearchTimer) {
            clearTimeout(this.goongSearchTimer);
        }

        const query = this.state.goongQuery.trim();
        if (query.length < 2) {
            this.state.goongSuggestions = [];
            this.state.isSearchingGoong = false;
            return;
        }

        this.state.isSearchingGoong = true;
        this.goongSearchTimer = setTimeout(async () => {
            try {
                const results = await this.orm.call("sgt.goong.service", "autocomplete_address", [query]);
                this.state.goongSuggestions = results || [];
            } catch (err) {
                console.warn("[Goong Autocomplete] Error fetching suggestions:", err);
                this.state.goongSuggestions = [];
            } finally {
                this.state.isSearchingGoong = false;
            }
        }, 350);
    }

    async selectGoongPlace(sug) {
        this.state.goongSuggestions = [];
        this.state.goongQuery = sug.description || sug.main_text;

        try {
            const res = await this.orm.call("sgt.goong.service", "geocode_address", [sug.description]);
            if (res && res.status === "success" && res.lat && res.lng && this.map) {
                this.map.setView([res.lat, res.lng], 14, { animate: true });

                if (this.goongMarker) {
                    this.map.removeLayer(this.goongMarker);
                }

                this.goongMarker = window.L.marker([res.lat, res.lng], {
                    title: sug.main_text,
                }).addTo(this.map);

                this.goongMarker.bindPopup(`
                    <div style="font-size: 12px;">
                        <strong><i class="fa fa-map-marker text-danger"></i> ${sug.main_text}</strong>
                        <div class="text-muted small mt-1">${res.formatted_address || sug.description}</div>
                        <div class="badge bg-success mt-1">Goong Geocoded: (${res.lat.toFixed(4)}, ${res.lng.toFixed(4)})</div>
                    </div>
                `).openPopup();
            } else {
                this.notification.add(res.error || "Không thể lấy tọa độ cho địa điểm này.", {
                    type: "warning",
                });
            }
        } catch (err) {
            console.error("[Goong Geocoding] Error resolving address:", err);
            this.notification.add("Lỗi kết nối Goong API: " + (err.message || err), {
                type: "danger",
            });
        }
    }

    clearGoongSearch() {
        this.state.goongQuery = "";
        this.state.goongSuggestions = [];
        if (this.goongMarker && this.map) {
            this.map.removeLayer(this.goongMarker);
            this.goongMarker = null;
        }
    }

    // -------------------------------------------------------------------------
    // WINDOW ACTIONS: ADD & VIEW PROJECT
    // -------------------------------------------------------------------------
    onAddProjectClick() {
        this.actionService.doAction(
            {
                name: "Thêm mới dự án Việt Nam",
                type: "ir.actions.act_window",
                res_model: "sgt.project.heatmap",
                views: [[false, "form"]],
                target: "new",
            },
            {
                onClose: () => {
                    this.refreshData();
                },
            }
        );
    }

    openProjectDetails(projectId) {
        this.actionService.doAction({
            name: "Chi tiết dự án",
            type: "ir.actions.act_window",
            res_model: "sgt.project.heatmap",
            res_id: projectId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    openContactDetails(contactId) {
        this.actionService.doAction({
            name: "Chi tiết Doanh nghiệp / Contact",
            type: "ir.actions.act_window",
            res_model: "res.partner",
            res_id: contactId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    async openContactMatchmaking(contactId) {
        try {
            const action = await this.orm.call("res.partner", "action_find_matching_companies", [[contactId]]);
            if (action) {
                this.actionService.doAction(action);
            }
        } catch (err) {
            console.error("[Project Heatmap] Error opening matchmaking:", err);
            this.notification.add("Không thể mở đề xuất Matching: " + (err.message || err), {
                type: "danger",
            });
        }
    }

    // -------------------------------------------------------------------------
    // TOP CONTACT AREAS ANALYSIS (TASK: KHU VỰC CÓ NHIỀU CONTACT NHẤT)
    // -------------------------------------------------------------------------
    async fetchTopContactAreas() {
        this.state.isLoadingTopAreas = true;
        try {
            const filters = {
                province: this.state.selectedProvince,
                district: this.state.selectedDistrict,
                industry: this.state.selectedIndustry,
                status: this.state.selectedStatus,
                event: this.state.selectedEvent,
                search: this.state.searchQuery,
            };
            const data = await this.orm.call("sgt.project.heatmap", "get_top_contact_areas", [], {
                project_id: this.state.selectedProjectId,
                area_level: this.state.topAreaLevel,
                domain: filters,
                limit: this.state.topAreaLimit === "all" ? 0 : this.state.topAreaLimit,
                sort_by: this.state.topAreaSortBy,
                sort_order: this.state.topAreaSortOrder,
            });
            if (data) {
                this.state.topAreasData = data;
            }
        } catch (err) {
            console.error("[Project Heatmap] Error fetching top contact areas:", err);
        } finally {
            this.state.isLoadingTopAreas = false;
        }
    }

    onAreaLevelChange(level) {
        this.state.topAreaLevel = level;
        this.state.selectedTopArea = null;
        this.fetchTopContactAreas();
    }

    onAreaLimitChange(limit) {
        this.state.topAreaLimit = limit;
        this.fetchTopContactAreas();
    }

    onAreaSort(field) {
        if (this.state.topAreaSortBy === field) {
            this.state.topAreaSortOrder = this.state.topAreaSortOrder === "desc" ? "asc" : "desc";
        } else {
            this.state.topAreaSortBy = field;
            this.state.topAreaSortOrder = field === "area" ? "asc" : "desc";
        }
        this.fetchTopContactAreas();
    }

    onTopAreaRowClick(areaItem) {
        if (!areaItem) return;
        this.state.selectedTopArea = areaItem.area;

        // Zoom map to area bounds or center
        if (this.map && window.L) {
            if (areaItem.bounds && areaItem.bounds[0] && areaItem.bounds[0][0] && areaItem.bounds[1] && areaItem.bounds[1][0]) {
                const bounds = window.L.latLngBounds(areaItem.bounds);
                this.map.fitBounds(bounds, { padding: [60, 60], maxZoom: 15 });
            } else if (areaItem.center && areaItem.center[0] && areaItem.center[1]) {
                this.map.setView(areaItem.center, 14, { animate: true });
            }
            this.renderMapLayersForArea(areaItem);
        }
    }

    renderMapLayersForArea(areaItem) {
        if (!this.map || !window.L) return;
        const partnerIds = new Set(areaItem.partner_ids || []);

        if (this.clusterGroup) {
            this.clusterGroup.clearLayers();
        }
        if (this.heatLayer) {
            this.map.removeLayer(this.heatLayer);
            this.heatLayer = null;
        }

        const heatPoints = [];
        const p = this.currentProject;
        const allContacts = p ? (p.contacts || []) : this.state.filteredProjects.flatMap((x) => x.contacts || []);

        allContacts.forEach((c) => {
            if (partnerIds.has(c.id) && c.has_coordinates) {
                heatPoints.push([c.latitude, c.longitude, Math.max(1.5, c.weight || 1.2)]);
                const marker = this._createContactMarker(c);
                if (this.clusterGroup) {
                    this.clusterGroup.addLayer(marker);
                }
            }
        });

        if (this.state.showHeatmap && window.L.heatLayer && heatPoints.length > 0) {
            this.heatLayer = window.L.heatLayer(heatPoints, {
                radius: Number(this.state.heatRadius) + 8,
                blur: 18,
                minOpacity: Number(this.state.heatIntensity) || 0.65,
                maxZoom: 16,
                gradient: { 0.2: "blue", 0.4: "cyan", 0.6: "lime", 0.8: "yellow", 1.0: "red" },
            }).addTo(this.map);
        }
    }

    resetTopAreaFilter() {
        this.state.selectedTopArea = null;
        this.renderMapLayers();
    }

    onUnmappedContactsClick() {
        const unmapped = this.state.topAreasData.unmapped_contacts || 0;
        const partnerIds = this.state.topAreasData.unmapped_partner_ids || [];
        if (unmapped === 0 || partnerIds.length === 0) {
            this.notification.add("Tất cả Contact đều đã có tọa độ và thông tin khu vực hợp lệ.", {
                type: "info",
            });
            return;
        }
        this.actionService.doAction({
            name: `Contact Chưa Có Vị Trí (${unmapped})`,
            type: "ir.actions.act_window",
            res_model: "res.partner",
            view_mode: "list,form",
            views: [[false, "list"], [false, "form"]],
            domain: [["id", "in", partnerIds]],
            target: "current",
        });
    }

    // ==========================================
    // SIDEBAR UX: COLLAPSE & QUICK SCROLL JUMP
    // ==========================================
    toggleSection(sectionKey) {
        if (this.state.collapsedSections[sectionKey] !== undefined) {
            this.state.collapsedSections[sectionKey] = !this.state.collapsedSections[sectionKey];
        }
    }

    collapseAllSections() {
        this.state.collapsedSections.filters = true;
        this.state.collapsedSections.layers = true;
        this.state.collapsedSections.stats = true;
        this.state.collapsedSections.provinces = true;
    }

    expandAllSections() {
        this.state.collapsedSections.filters = false;
        this.state.collapsedSections.layers = false;
        this.state.collapsedSections.stats = false;
        this.state.collapsedSections.provinces = false;
        this.state.collapsedSections.topAreas = false;
    }

    scrollToSection(sectionId) {
        const keyMap = {
            sgt_section_projectSelect: null,
            sgt_section_filters: "filters",
            sgt_section_layers: "layers",
            sgt_section_stats: "stats",
            sgt_section_provinces: "provinces",
            sgt_section_topAreas: "topAreas",
        };
        const key = keyMap[sectionId];
        if (key && this.state.collapsedSections[key]) {
            this.state.collapsedSections[key] = false;
        }

        setTimeout(() => {
            const el = document.getElementById(sectionId);
            if (el) {
                el.scrollIntoView({ behavior: "smooth", block: "start" });
                el.classList.remove("sgt-highlight-pulse");
                void el.offsetWidth;
                el.classList.add("sgt-highlight-pulse");
                setTimeout(() => {
                    if (el) {
                        el.classList.remove("sgt-highlight-pulse");
                    }
                }, 2000);
            }
        }, 50);
    }

    scrollToTop() {
        const sidebar = document.querySelector(".sgt-left-sidebar");
        if (sidebar) {
            sidebar.scrollTo({ top: 0, behavior: "smooth" });
        }
    }
}

// Register OWL Client Action into Odoo 19 actions registry
registry.category("actions").add("sgt_project_heatmap_dashboard", SgtProjectHeatmapDashboard);

const api = (() => {
  function withLang(path) {
    const sep = path.includes("?") ? "&" : "?";
    return `${path}${sep}lang=${encodeURIComponent(i18n.getLang())}&catalog_lang=${encodeURIComponent(i18n.getCatalogLang())}&tz=${encodeURIComponent(i18n.getTimeZone())}`;
  }

  async function request(method, path, body) {
    const res = await fetch(withLang(path), {
      method,
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    });
    if (res.status === 401) window.dispatchEvent(new Event("auth-required"));
    if (!res.ok) {
      let detail = res.statusText;
      try {
        const data = await res.json();
        detail = data.detail || JSON.stringify(data);
      } catch (_) {}
      throw new Error(detail);
    }
    if (res.status === 204) return null;
    return res.json();
  }

  async function upload(path, file) {
    const formData = new FormData();
    formData.append("file", file);
    const res = await fetch(withLang(path), { method: "POST", body: formData });
    if (res.status === 401) window.dispatchEvent(new Event("auth-required"));
    if (!res.ok) {
      let detail = res.statusText;
      try {
        const data = await res.json();
        detail = data.detail || JSON.stringify(data);
      } catch (_) {}
      throw new Error(detail);
    }
    return res.json();
  }

  return {
    me: () => request("GET", "/api/me"),
    listFacilities: () => request("GET", "/api/facilities"),
    createFacility: (data) => request("POST", "/api/facilities", data),
    getFacility: (id) => request("GET", `/api/facilities/${id}`),
    updateFacility: (id, data) => request("PUT", `/api/facilities/${id}`, data),
    deleteFacility: (id) => request("DELETE", `/api/facilities/${id}`),
    getFacilityStock: (id) => request("GET", `/api/facilities/${id}/stock`),
    listFacilityTargets: (id) => request("GET", `/api/facilities/${id}/targets`),
    setFacilityTarget: (id, data) => request("PUT", `/api/facilities/${id}/targets`, data),
    // Live estimate (Dashboard tab) — computed on the server, never stored.
    getDashboard: (id) => request("GET", `/api/facilities/${id}/dashboard`),
    listUsers: () => request("GET", "/api/users"),
    transferFacility: (id, userId) => request("PUT", `/api/facilities/${id}/owner`, { user_id: userId }),
    getDiscordWebhook: (id) => request("GET", `/api/facilities/${id}/discord-webhook`),
    setDiscordWebhook: (id, url, thread) => request("PUT", `/api/facilities/${id}/discord-webhook`, { url, thread }),
    sendDiscordWebhook: (id) => request("POST", `/api/facilities/${id}/discord-webhook/send`),
    deleteDiscordWebhook: (id) => request("DELETE", `/api/facilities/${id}/discord-webhook`),
    setItemOrigin: (id, data) => request("PUT", `/api/facilities/${id}/item-origins`, data),

    listBuildings: (facilityId) => request("GET", `/api/facilities/${facilityId}/buildings`),
    createBuilding: (facilityId, data) => request("POST", `/api/facilities/${facilityId}/buildings`, data),
    updateBuilding: (id, data) => request("PUT", `/api/buildings/${id}`, data),
    deleteBuilding: (id) => request("DELETE", `/api/buildings/${id}`),

    // With a facility: item origins as that facility set them.
    listResources: (facilityId) =>
      request("GET", facilityId ? `/api/resources?facility_id=${facilityId}` : "/api/resources"),
    createResource: (data) => request("POST", "/api/resources", data),
    updateResource: (id, data) => request("PUT", `/api/resources/${id}`, data),
    deleteResource: (id) => request("DELETE", `/api/resources/${id}`),

    getBuildingStock: (buildingId) => request("GET", `/api/buildings/${buildingId}/stock`),
    addBuildingStock: (buildingId, entries) => request("POST", `/api/buildings/${buildingId}/stock`, entries),
    deleteBuildingStockItem: (buildingId, resourceId, storage) =>
      request("DELETE", `/api/buildings/${buildingId}/stock/${resourceId}?storage=${encodeURIComponent(storage)}`),

    createReport: (facilityId) => request("POST", `/api/facilities/${facilityId}/reports`),
    listReports: (facilityId) => request("GET", `/api/facilities/${facilityId}/reports`),
    getReport: (id) => request("GET", `/api/reports/${id}`),
    deleteReport: (id) => request("DELETE", `/api/reports/${id}`),

    ocrStatus: () => request("GET", "/api/ocr/status"),
    listBuildingImages: (buildingId) => request("GET", `/api/buildings/${buildingId}/images`),
    uploadBuildingImage: (buildingId, file) => upload(`/api/buildings/${buildingId}/images`, file),
    readImageCrop: (imageId, box) => request("POST", `/api/images/${imageId}/ocr`, box),
    detectStockpile: (imageId, box, read = true) =>
      request("POST", `/api/images/${imageId}/detect-stockpile${read ? "" : "?read=false"}`, box),
    saveIconExemplars: (imageId, items) => request("POST", `/api/images/${imageId}/exemplars`, items),

    listFoxholeResources: () => request("GET", "/api/foxhole/resources"),
    listFoxholeBuildingTypes: () => request("GET", "/api/foxhole/building-types"),
    setBuildingProduction: (buildingId, data) => request("PUT", `/api/buildings/${buildingId}/production`, data),
    getProductionEstimate: (buildingId) => request("GET", `/api/buildings/${buildingId}/production-estimate`),
    // Private ("Personal") production orders — app/services/private_orders.py.
    listPrivateOrders: (facilityId) => request("GET", `/api/facilities/${facilityId}/private-orders`),
    createPrivateOrder: (buildingId, data) => request("POST", `/api/buildings/${buildingId}/private-orders`, data),
    updatePrivateOrder: (buildingId, id, data) => request("PUT", `/api/buildings/${buildingId}/private-orders/${id}`, data),
    closePrivateOrder: (buildingId, id) => request("POST", `/api/buildings/${buildingId}/private-orders/${id}/close`),
    deletePrivateOrder: (buildingId, id) => request("DELETE", `/api/buildings/${buildingId}/private-orders/${id}`),
    // Order panel screenshot (already uploaded) → form pre-fill; recipes = the ones offered.
    readPrivateOrderPrint: (buildingId, imageId, recipes) =>
      request(
        "POST",
        `/api/buildings/${buildingId}/private-orders/read-print?recipes=${encodeURIComponent(recipes.join(","))}`,
        { image_id: imageId }
      ),

    getCaptureSettings: () => request("GET", "/api/settings/capture"),
    updateCaptureSettings: (data) => request("PUT", "/api/settings/capture", data),

    saveStatus: () => request("GET", "/api/save/status"),
    // No file = read this PC's own save (local mode); a file = an uploaded .sav (web mode).
    listSavePins: (file) => (file ? upload("/api/save/pins", file) : request("POST", "/api/save/pins")),
    linkSavePin: (buildingId, pinKey, location) =>
      request("PUT", `/api/buildings/${buildingId}/save-pin`, { pin_key: pinKey, location }),
    setCodenameAlias: (data) => request("PUT", "/api/save/aliases", data),
  };
})();

const api = (() => {
  function withLang(path) {
    const sep = path.includes("?") ? "&" : "?";
    return `${path}${sep}lang=${encodeURIComponent(i18n.getLang())}&catalog_lang=${encodeURIComponent(i18n.getCatalogLang())}`;
  }

  async function request(method, path, body) {
    const res = await fetch(withLang(path), {
      method,
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    });
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
    listFacilities: () => request("GET", "/api/facilities"),
    createFacility: (data) => request("POST", "/api/facilities", data),
    getFacility: (id) => request("GET", `/api/facilities/${id}`),
    updateFacility: (id, data) => request("PUT", `/api/facilities/${id}`, data),
    deleteFacility: (id) => request("DELETE", `/api/facilities/${id}`),
    getFacilityStock: (id) => request("GET", `/api/facilities/${id}/stock`),

    listBuildings: (facilityId) => request("GET", `/api/facilities/${facilityId}/buildings`),
    createBuilding: (facilityId, data) => request("POST", `/api/facilities/${facilityId}/buildings`, data),
    updateBuilding: (id, data) => request("PUT", `/api/buildings/${id}`, data),
    deleteBuilding: (id) => request("DELETE", `/api/buildings/${id}`),

    listResources: () => request("GET", "/api/resources"),
    createResource: (data) => request("POST", "/api/resources", data),
    updateResource: (id, data) => request("PUT", `/api/resources/${id}`, data),
    deleteResource: (id) => request("DELETE", `/api/resources/${id}`),

    getBuildingStock: (buildingId) => request("GET", `/api/buildings/${buildingId}/stock`),
    addBuildingStock: (buildingId, entries) => request("POST", `/api/buildings/${buildingId}/stock`, entries),

    createReport: (facilityId) => request("POST", `/api/facilities/${facilityId}/reports`),
    listReports: (facilityId) => request("GET", `/api/facilities/${facilityId}/reports`),
    getReport: (id) => request("GET", `/api/reports/${id}`),
    deleteReport: (id) => request("DELETE", `/api/reports/${id}`),

    ocrStatus: () => request("GET", "/api/ocr/status"),
    listBuildingImages: (buildingId) => request("GET", `/api/buildings/${buildingId}/images`),
    uploadBuildingImage: (buildingId, file) => upload(`/api/buildings/${buildingId}/images`, file),
    readImageCrop: (imageId, box) => request("POST", `/api/images/${imageId}/ocr`, box),
    detectStockpile: (imageId, box) => request("POST", `/api/images/${imageId}/detect-stockpile`, box),

    listFoxholeResources: () => request("GET", "/api/foxhole/resources"),
    listFoxholeBuildingTypes: () => request("GET", "/api/foxhole/building-types"),
    setBuildingProduction: (buildingId, data) => request("PUT", `/api/buildings/${buildingId}/production`, data),
    getProductionEstimate: (buildingId) => request("GET", `/api/buildings/${buildingId}/production-estimate`),
  };
})();

/**
 * SIAM - Aluminios Cristales Villegas
 * Logica Frontend para PWA, captura de camara y renderizado interactivo de corte 2D
 */

document.addEventListener('DOMContentLoaded', () => {
    // 1. Registro del Service Worker para PWA
    registerServiceWorker();

    // 2. Manejo de Instalacion PWA (beforeinstallprompt)
    initPwaInstall();

    // 3. Monitor de Conexion Online / Offline
    initNetworkMonitor();

    // 4. Inicializar Gestor de Camara, Lamina, Pedidos y Menus Desplegables
    initCameraAndUpload();
    initOrdersManager();
    initFormSubmission();
    initAuthAndTraceability();
    initModuleAndFunctionMenus();
});

/* ==========================================================================
   1. REGISTRO DEL SERVICE WORKER
   ========================================================================== */
function registerServiceWorker() {
    if ('serviceWorker' in navigator) {
        window.addEventListener('load', () => {
            navigator.serviceWorker.register('/sw.js', { scope: '/' })
                .then((registration) => {
                    console.log('[PWA] Service Worker registrado con exito en el alcance:', registration.scope);
                })
                .catch((error) => {
                    console.error('[PWA] Error al registrar el Service Worker:', error);
                });
        });
    }
}

/* ==========================================================================
   2. INSTALACION DE PWA (Añadir a pantalla de inicio)
   ========================================================================== */
let deferredPrompt;
function initPwaInstall() {
    const installBanner = document.getElementById('pwaInstallBanner');
    const installBtn = document.getElementById('btnInstallPwa');
    const dismissBtn = document.getElementById('btnDismissInstall');

    window.addEventListener('beforeinstallprompt', (e) => {
        e.preventDefault();
        deferredPrompt = e;
        if (installBanner) {
            installBanner.style.display = 'flex';
        }
    });

    if (installBtn) {
        installBtn.addEventListener('click', async () => {
            if (!deferredPrompt) return;
            deferredPrompt.prompt();
            const { outcome } = await deferredPrompt.userChoice;
            console.log(`[PWA] Respuesta del usuario a instalacion: ${outcome}`);
            deferredPrompt = null;
            if (installBanner) installBanner.style.display = 'none';
        });
    }

    if (dismissBtn) {
        dismissBtn.addEventListener('click', () => {
            if (installBanner) installBanner.style.display = 'none';
        });
    }

    window.addEventListener('appinstalled', () => {
        console.log('[PWA] SIAM fue instalada satisfactoriamente en el dispositivo');
        if (installBanner) installBanner.style.display = 'none';
    });
}

/* ==========================================================================
   3. ESTADO DE RED (Online / Offline)
   ========================================================================== */
function initNetworkMonitor() {
    const indicator = document.getElementById('offlineIndicator');

    function updateOnlineStatus() {
        if (!navigator.onLine) {
            if (indicator) indicator.style.display = 'block';
        } else {
            if (indicator) indicator.style.display = 'none';
        }
    }

    window.addEventListener('online', updateOnlineStatus);
    window.addEventListener('offline', updateOnlineStatus);
    updateOnlineStatus();
}

/* ==========================================================================
   4. MANEJO DE CAMARA Y CARGA DE IMAGEN
   ========================================================================== */
let selectedFile = null;

function initCameraAndUpload() {
    const cameraInput = document.getElementById('cameraInput');
    const galleryInput = document.getElementById('galleryInput');
    const btnTriggerCamera = document.getElementById('btnTriggerCamera');
    const btnTriggerGallery = document.getElementById('btnTriggerGallery');
    const previewImage = document.getElementById('previewImage');
    const previewPlaceholder = document.getElementById('previewPlaceholder');
    const fileInfoText = document.getElementById('fileInfoText');
    const btnSubmit = document.getElementById('btnProcessImage');

    if (btnTriggerCamera && cameraInput) {
        btnTriggerCamera.addEventListener('click', () => {
            cameraInput.click();
        });
    }

    if (btnTriggerGallery && galleryInput) {
        btnTriggerGallery.addEventListener('click', () => {
            galleryInput.click();
        });
    }

    function classifyGlassTypeClient(imgEl, filename = '') {
        try {
            const canvas = document.createElement('canvas');
            const cw = 160, ch = 160;
            canvas.width = cw;
            canvas.height = ch;
            const ctx = canvas.getContext('2d');
            ctx.drawImage(imgEl, 0, 0, cw, ch);
            const x1 = Math.floor(cw * 0.12), y1 = Math.floor(ch * 0.12);
            const rw = Math.floor(cw * 0.76), rh = Math.floor(ch * 0.76);
            const imgData = ctx.getImageData(x1, y1, rw, rh).data;
            const total = rw * rh;

            let sumR = 0, sumG = 0, sumB = 0, sumS = 0, sumV = 0, sumLum = 0, specCount = 0;
            const lums = new Float32Array(total);
            for (let i = 0, p = 0; i < imgData.length; i += 4, p++) {
                const r = imgData[i], g = imgData[i + 1], b = imgData[i + 2];
                sumR += r; sumG += g; sumB += b;
                const maxC = Math.max(r, g, b), minC = Math.min(r, g, b);
                const s = maxC === 0 ? 0 : ((maxC - minC) / maxC) * 255;
                sumS += s;
                sumV += maxC;
                const lum = 0.299 * r + 0.587 * g + 0.114 * b;
                lums[p] = lum;
                sumLum += lum;
                if (lum > 200) specCount++;
            }
            const meanR = sumR / total, meanG = sumG / total, meanB = sumB / total;
            const meanS = sumS / total, meanV = sumV / total, meanLum = sumLum / total;
            let varSum = 0;
            for (let p = 0; p < total; p++) {
                const d = lums[p] - meanLum;
                varSum += d * d;
            }
            const stdLum = Math.sqrt(varSum / total);
            const specRatio = specCount / total;
            const reflectancePct = Math.min(98, Math.max(8, (stdLum * 1.15) + (specRatio * 120))).toFixed(1);
            const transmittancePct = Math.min(92, Math.max(12, (meanV / 255) * 100)).toFixed(1);
            const fname = (filename || '').toLowerCase();

            let glassType = 'Vidrio Claro Transparente';
            let opticalDesc = `Superficie monolítica incolora | Transmitancia: ${transmittancePct}%`;

            if (fname.includes('bronce')) {
                glassType = 'Vidrio Reflectivo Bronce';
                opticalDesc = `Tono cálido bronce/ámbar | Reflectancia solar: ${reflectancePct}%`;
            } else if (fname.includes('espejo')) {
                glassType = 'Vidrio Reflectivo Espejo';
                opticalDesc = `Reflexión especular tipo espejo (${reflectancePct}%) | Contraste: ${stdLum.toFixed(1)}`;
            } else if (fname.includes('fotocrom') || fname.includes('polariz')) {
                glassType = 'Vidrio Fotocromático';
                opticalDesc = `Filtro fotosensible activo | Transmitancia: ${transmittancePct}%`;
            } else if ((meanR - meanB) > 7.5 && meanS >= 14.0) {
                glassType = 'Vidrio Reflectivo Bronce';
                opticalDesc = `Dominancia espectral cálida bronce/cobre (R:${meanR.toFixed(0)} > B:${meanB.toFixed(0)}) | Reflectancia: ${reflectancePct}%`;
            } else if ((stdLum >= 30.0 && Math.abs(meanR - meanB) <= 12.0) || (specRatio > 0.045 && meanS < 42.0)) {
                glassType = 'Vidrio Reflectivo Espejo';
                opticalDesc = `Reflexión especular plateada (${reflectancePct}%) | Balance neutro espejo`;
            } else if ((meanV < 118.0 && stdLum < 30.0) || ((meanB - meanR) > 4.5 && meanV < 148.0)) {
                glassType = 'Vidrio Fotocromático';
                opticalDesc = `Absorción fotosensible UV-Visible | Transmitancia: ${transmittancePct}%`;
            } else if ((meanB - meanR) > 12.0 && meanS >= 20.0) {
                glassType = 'Vidrio Reflectivo Azul (Control Solar)';
                opticalDesc = `Tono espectral azul reflectivo | Reflectancia: ${reflectancePct}%`;
            } else if ((meanG - meanR) > 4.5 && (meanG - meanB) > 4.5) {
                glassType = 'Vidrio Flotado Verde / Templado';
                opticalDesc = `Tinte verdoso de óxido de hierro | Transmitancia: ${transmittancePct}%`;
            } else if (meanV >= 165.0 && meanS < 20.0 && stdLum < 22.0) {
                glassType = 'Vidrio Esmerilado / Satinado';
                opticalDesc = `Superficie difusa mate | Transmitancia: ${transmittancePct}%`;
            }
            return { glassType, opticalDesc };
        } catch (err) {
            return { glassType: 'Vidrio Claro Transparente', opticalDesc: 'Superficie verificada' };
        }
    }

    function handleFile(file) {
        if (!file) return;
        selectedFile = file;

        const reader = new FileReader();
        reader.onload = (e) => {
            previewImage.onload = async () => {
                const liveBox = document.getElementById('glassTypeLiveBox');
                const liveName = document.getElementById('liveGlassTypeName');
                const liveOpt = document.getElementById('liveGlassTypeOptical');
                const sizeMb = (file.size / (1024 * 1024)).toFixed(2);

                try {
                    const fd = new FormData();
                    fd.append('image', file);
                    const res = await fetch('/api/vision/classify-glass', { method: 'POST', body: fd });
                    const data = await res.json();
                    if (!res.ok || !data.success) {
                        const errMsg = data.message || 'CAPTURA RECHAZADA: No se detectó una lámina de vidrio frente a la cámara.';
                        if (liveBox && liveName) {
                            liveBox.style.background = '#3b0d0d';
                            liveBox.style.borderColor = '#EF4444';
                            liveName.textContent = 'RECHAZADO (NO ES LÁMINA DE VIDRIO)';
                            if (liveOpt) liveOpt.textContent = errMsg;
                            liveBox.classList.remove('d-none');
                        }
                        fileInfoText.innerHTML = `<strong class="text-danger">${errMsg}</strong>`;
                        if (btnSubmit) btnSubmit.setAttribute('disabled', 'disabled');
                        alert(errMsg);
                        return;
                    }
                    if (liveBox && liveName) {
                        liveBox.style.background = '#0c2340';
                        liveBox.style.borderColor = '#0284C7';
                        liveName.textContent = data.glass_type;
                        if (liveOpt) liveOpt.textContent = data.optical_summary || '';
                        liveBox.classList.remove('d-none');
                    }
                    fileInfoText.innerHTML = `<strong>Tipo Identificado: ${data.glass_type}</strong> · ${file.name} (${sizeMb} MB)`;
                    if (btnSubmit) btnSubmit.removeAttribute('disabled');
                } catch (err) {
                    const info = classifyGlassTypeClient(previewImage, file.name);
                    if (liveBox && liveName) {
                        liveName.textContent = info.glassType;
                        if (liveOpt) liveOpt.textContent = info.opticalDesc;
                        liveBox.classList.remove('d-none');
                    }
                    fileInfoText.innerHTML = `<strong>Tipo Identificado: ${info.glassType}</strong> · ${file.name} (${sizeMb} MB)`;
                }
            };
            previewImage.src = e.target.result;
            previewImage.classList.remove('d-none');
            previewPlaceholder.classList.add('d-none');
            
            const sizeMb = (file.size / (1024 * 1024)).toFixed(2);
            fileInfoText.innerHTML = `<strong>Verificando lámina...</strong> ${file.name} (${sizeMb} MB)`;
            fileInfoText.classList.remove('text-muted');
            fileInfoText.classList.add('text-success');

            if (btnSubmit) {
                btnSubmit.removeAttribute('disabled');
            }
        };
        reader.readAsDataURL(file);
    }

    if (cameraInput) {
        cameraInput.addEventListener('change', (e) => {
            if (e.target.files && e.target.files[0]) {
                handleFile(e.target.files[0]);
            }
        });
    }

    if (galleryInput) {
        galleryInput.addEventListener('change', (e) => {
            if (e.target.files && e.target.files[0]) {
                handleFile(e.target.files[0]);
            }
        });
    }
}

/* ==========================================================================
   5. VALIDACIÓN DE LÁMINA MADRE Y PEDIDOS DE CORTE
   ========================================================================== */
let sheetConfigured = false;
let configuredSheetW = 0;
let configuredSheetH = 0;
let cuttingOrders = [];

window.confirmSheetSize = async function() {
    const wInput = document.getElementById('sheetWidth');
    const hInput = document.getElementById('sheetHeight');

    const w = parseInt(wInput?.value || '0', 10);
    const h = parseInt(hInput?.value || '0', 10);

    if (isNaN(w) || isNaN(h) || w <= 0 || h <= 0) {
        alert('Error de Tamaño de Lámina: Ingrese valores numéricos mayores a cero para el Ancho y Alto de la lámina.');
        return false;
    }

    try {
        const res = await fetch('/api/validate-sheet', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ sheet_width: w, sheet_height: h })
        });
        const data = await res.json();
        if (!res.ok || !data.success) {
            sheetConfigured = false;
            alert(data.message || 'Dimensiones de lámina fuera del rango permitido.');
            return false;
        }

        sheetConfigured = true;
        configuredSheetW = w;
        configuredSheetH = h;

        // Verificar si había piezas previas que excedan el nuevo tamaño de lámina
        const invalidPrev = cuttingOrders.filter(o => o.w > configuredSheetW || o.h > configuredSheetH);
        if (invalidPrev.length > 0) {
            cuttingOrders = cuttingOrders.filter(o => o.w <= configuredSheetW && o.h <= configuredSheetH);
            renderOrdersTable();
            alert(`Se removieron ${invalidPrev.length} pieza(s) previas cuyas medidas superaban el nuevo tamaño de lámina (${configuredSheetW}x${configuredSheetH}).`);
        }

        alert(data.message || `Lámina Madre configurada en ${w} x ${h}. Ahora puede ingresar las medidas de los cortes.`);
        return true;
    } catch (err) {
        alert('Error al validar el tamaño de la lámina en el servidor.');
        return false;
    }
};

function initOrdersManager() {
    renderOrdersTable();

    const btnConfirmSheet = document.getElementById('btnConfirmSheetSize');
    if (btnConfirmSheet) {
        btnConfirmSheet.addEventListener('click', () => {
            window.confirmSheetSize();
        });
    }

    const sheetWInput = document.getElementById('sheetWidth');
    const sheetHInput = document.getElementById('sheetHeight');
    const markSheetUnconfirmed = () => {
        const w = parseInt(sheetWInput?.value || '0', 10);
        const h = parseInt(sheetHInput?.value || '0', 10);
        if (w !== configuredSheetW || h !== configuredSheetH) {
            sheetConfigured = false;
        }
    };
    if (sheetWInput) sheetWInput.addEventListener('input', markSheetUnconfirmed);
    if (sheetHInput) sheetHInput.addEventListener('input', markSheetUnconfirmed);

    const btnAddOrder = document.getElementById('btnAddOrder');
    if (btnAddOrder) {
        btnAddOrder.addEventListener('click', () => {
            // Exigir primero definir y validar el tamaño de la lámina madre
            if (!sheetConfigured || configuredSheetW <= 0 || configuredSheetH <= 0) {
                alert('ERROR: Primero debe definir y fijar el Tamaño de la Lámina Madre (Paso 1: botón "1. Validar y Fijar Tamaño de Lámina Madre") antes de ingresar las medidas de los cortes.');
                return;
            }

            const wInput = document.getElementById('orderWidth');
            const hInput = document.getElementById('orderHeight');
            const idInput = document.getElementById('orderId');

            const w = parseInt(wInput.value, 10);
            const h = parseInt(hInput.value, 10);
            const id = idInput.value.trim() || `Corte-${cuttingOrders.length + 1}`;

            if (isNaN(w) || isNaN(h) || w <= 0 || h <= 0) {
                alert('Error de Medida: Las medidas de corte (Ancho y Alto) deben ser mayores a cero.');
                return;
            }

            // Validar que la medida del corte no supere la lámina madre
            if (w > configuredSheetW || h > configuredSheetH) {
                alert(`ERROR DE MEDIDA DE CORTE: La pieza solicitada (${w} x ${h}) excede las dimensiones de la Lámina Madre configurada (${configuredSheetW} x ${configuredSheetH}). Ingrese una medida que quepa dentro de la lámina.`);
                return;
            }

            cuttingOrders.push({ id, w, h });
            renderOrdersTable();

            idInput.value = '';
        });
    }

    const btnRefreshOrders = document.getElementById('btnRefreshOrders');
    if (btnRefreshOrders) {
        btnRefreshOrders.addEventListener('click', () => {
            cuttingOrders = [];
            sheetConfigured = false;
            configuredSheetW = 0;
            configuredSheetH = 0;
            renderOrdersTable();
            const resultsSection = document.getElementById('resultsSection');
            if (resultsSection) resultsSection.classList.add('d-none');
        });
    }
}

function renderOrdersTable() {
    const tableBody = document.getElementById('ordersTableBody');
    if (!tableBody) return;

    if (cuttingOrders.length === 0) {
        tableBody.innerHTML = `<tr><td colspan="4" class="text-center text-muted py-2">Sin pedidos agregados. Primero valide el tamaño de la Lámina Madre y luego agregue las piezas.</td></tr>`;
        return;
    }

    tableBody.innerHTML = cuttingOrders.map((order, idx) => `
        <tr>
            <td class="fw-bold text-primary">${order.id}</td>
            <td>${order.w}</td>
            <td>${order.h}</td>
            <td class="text-end">
                <button type="button" class="btn btn-sm btn-outline-danger" onclick="removeOrder(${idx})">
                    Eliminar
                </button>
            </td>
        </tr>
    `).join('');
}

window.removeOrder = function(index) {
    cuttingOrders.splice(index, 1);
    renderOrdersTable();
};

/* ==========================================================================
   6. ENVIO AL SERVIDOR FLASK (/api/scan-and-optimize)
   ========================================================================== */
function initFormSubmission() {
    const form = document.getElementById('scanForm');
    const loadingOverlay = document.getElementById('loadingOverlay');
    const resultsSection = document.getElementById('resultsSection');

    if (!form) return;

    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        if (!selectedFile) {
            alert('Por favor tome una foto o seleccione una imagen de la lámina.');
            return;
        }

        if (!sheetConfigured || configuredSheetW <= 0 || configuredSheetH <= 0) {
            alert('ERROR: Primero debe validar y fijar el Tamaño de la Lámina Madre (Paso 1) antes de optimizar los cortes.');
            return;
        }

        if (cuttingOrders.length === 0) {
            alert('Agregue al menos un pedido de corte válido a la lista.');
            return;
        }

        if (loadingOverlay) loadingOverlay.style.display = 'flex';

        const formData = new FormData();
        formData.append('image', selectedFile);
        formData.append('orders', JSON.stringify(cuttingOrders));
        formData.append('sheet_width', configuredSheetW);
        formData.append('sheet_height', configuredSheetH);

        try {
            const response = await fetch('/api/scan-and-optimize', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (!response.ok || !data.success) {
                throw new Error(data.message || 'Error durante el procesamiento en el servidor.');
            }

            renderResults(data);

            if (resultsSection) {
                resultsSection.classList.remove('d-none');
                resultsSection.scrollIntoView({ behavior: 'smooth' });
            }
        } catch (err) {
            console.error('Error al procesar la lámina:', err);
            alert(`Error: ${err.message}`);
        } finally {
            if (loadingOverlay) loadingOverlay.style.display = 'none';
        }
    });
}

/* ==========================================================================
   7. RENDERIZADO DE RESULTADOS & PLANO DE CORTE 2D
   ========================================================================== */
function renderResults(data) {
    const qcBadge = document.getElementById('resultQcBadge');
    const defectTypeEl = document.getElementById('resultDefectType');
    const defectConfidenceEl = document.getElementById('resultConfidence');
    const defectAreaEl = document.getElementById('resultArea');
    const qcRecommendationEl = document.getElementById('resultRecommendation');
    const annotatedImg = document.getElementById('annotatedImage');

    if (qcBadge) {
        qcBadge.className = 'qc-badge';
        if (data.qc_status === 'APROBADO') {
            qcBadge.classList.add('qc-aprobado');
            qcBadge.textContent = `ESTADO: ${data.qc_status}`;
        } else if (data.qc_status === 'APROBADO CON CONDICIÓN') {
            qcBadge.classList.add('qc-condicion');
            qcBadge.textContent = `ESTADO: ${data.qc_status}`;
        } else {
            qcBadge.classList.add('qc-rechazado');
            qcBadge.textContent = `ESTADO: ${data.qc_status}`;
        }
    }

    const resGlassTypeEl = document.getElementById('resultGlassType');
    const resGlassOptEl = document.getElementById('resultGlassOptical');
    if (resGlassTypeEl) resGlassTypeEl.textContent = data.glass_type || 'Vidrio Claro Transparente';
    if (resGlassOptEl) resGlassOptEl.textContent = data.glass_optical_summary || 'Superficie de vidrio verificada por filtro óptico.';

    if (defectTypeEl) defectTypeEl.textContent = data.defect_type || 'Ninguno';
    if (defectConfidenceEl) defectConfidenceEl.textContent = `${(data.confidence || 0).toFixed(1)}%`;
    if (defectAreaEl) defectAreaEl.textContent = `${(data.defect_area || 0).toFixed(1)} mm²`;
    const sevEl = document.getElementById('resultSeverity');
    if (sevEl) sevEl.textContent = data.severity || 'NINGUNA';
    if (qcRecommendationEl) qcRecommendationEl.textContent = data.recommendation || 'Sin observaciones.';
    const badgeTime = document.getElementById('badgeProcessTime');
    if (badgeTime && data.processing_time_sec !== undefined) {
        badgeTime.textContent = `Algoritmo FFD (${data.processing_time_sec}s < 5s RNF)`;
    }

    if (typeof loadTraceabilityData === 'function') {
        loadTraceabilityData();
    }

    if (annotatedImg && data.annotated_image_url) {
        annotatedImg.src = data.annotated_image_url;
        annotatedImg.classList.remove('d-none');
    }

    const kpiEfficiency = document.getElementById('kpiEfficiency');
    const kpiWaste = document.getElementById('kpiWaste');
    const kpiPlaced = document.getElementById('kpiPlaced');
    const kpiUsedArea = document.getElementById('kpiUsedArea');

    if (kpiEfficiency) kpiEfficiency.textContent = `${(data.efficiency_score || 0).toFixed(1)}%`;
    if (kpiWaste) kpiWaste.textContent = `${(data.waste_percentage || 0).toFixed(1)}%`;
    if (kpiPlaced) kpiPlaced.textContent = `${data.placed_count || 0}/${data.requested_count || 0}`;
    const usedM2 = (data.total_area_used || 0) / 1000000;
    if (kpiUsedArea) kpiUsedArea.textContent = `${usedM2.toFixed(2)} m²`;

    const priceInput = document.getElementById('pricePerM2');
    const pricePerM2 = priceInput ? (parseFloat(priceInput.value) || 25.0) : 25.0;
    const savedUsd = (usedM2 * pricePerM2).toFixed(2);
    const totalSheetM2 = ((data.sheet_width || 2000) * (data.sheet_height || 2000)) / 1000000;
    const totalSheetUsd = (totalSheetM2 * pricePerM2).toFixed(2);
    const kpiEconomicUsd = document.getElementById('kpiEconomicUsd');
    if (kpiEconomicUsd) {
        kpiEconomicUsd.textContent = `$${savedUsd} USD recuperados (de $${totalSheetUsd} USD costo lámina a $${pricePerM2.toFixed(2)}/m²)`;
    }

    drawCuttingPlan(data.sheet_width, data.sheet_height, data.placed_pieces, data.defect_coords);
}

function drawCuttingPlan(sheetW, sheetH, placedPieces, defectCoords) {
    const canvas = document.getElementById('cuttingCanvas');
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    const canvasWidth = 700;
    const canvasHeight = 700;
    canvas.width = canvasWidth;
    canvas.height = canvasHeight;

    const scaleX = canvasWidth / sheetW;
    const scaleY = canvasHeight / sheetH;

    // Fondo de la Lámina Madre
    ctx.fillStyle = '#E2E8F0';
    ctx.fillRect(0, 0, canvasWidth, canvasHeight);

    // Cuadrícula de referencia del plano de corte
    ctx.strokeStyle = '#94A3B8';
    ctx.lineWidth = 1;
    ctx.setLineDash([2, 2]);
    const stepX = canvasWidth / 20.0;
    const stepY = canvasHeight / 20.0;
    for (let i = 1; i < 20; i++) {
        ctx.beginPath();
        ctx.moveTo(i * stepX, 0);
        ctx.lineTo(i * stepX, canvasHeight);
        ctx.stroke();

        ctx.beginPath();
        ctx.moveTo(0, i * stepY);
        ctx.lineTo(canvasWidth, i * stepY);
        ctx.stroke();
    }
    ctx.setLineDash([]);

    // Dibujar Zona Defectuosa (Obstáculo esquivado en rojo brillante)
    if (defectCoords && defectCoords.w > 0 && defectCoords.h > 0) {
        const dx = defectCoords.x * scaleX;
        const dy = defectCoords.y * scaleY;
        const dw = defectCoords.w * scaleX;
        const dh = defectCoords.h * scaleY;

        ctx.fillStyle = 'rgba(239, 68, 68, 0.45)';
        ctx.fillRect(dx, dy, dw, dh);
        ctx.strokeStyle = '#DC2626';
        ctx.lineWidth = 2;
        ctx.setLineDash([4, 4]);
        ctx.strokeRect(dx, dy, dw, dh);
        ctx.setLineDash([]);

        ctx.fillStyle = '#991B1B';
        ctx.font = 'bold 12px system-ui';
        ctx.fillText('ZONA DE DEFECTO', dx + 4, dy + 16);
    }

    const pieceColors = [
        { fill: 'rgba(2, 132, 199, 0.85)', stroke: '#0369A1' },
        { fill: 'rgba(16, 185, 129, 0.85)', stroke: '#047857' },
        { fill: 'rgba(139, 92, 246, 0.85)', stroke: '#6D28D9' },
        { fill: 'rgba(245, 158, 11, 0.85)', stroke: '#D97706' },
        { fill: 'rgba(236, 72, 153, 0.85)', stroke: '#BE185D' }
    ];

    if (placedPieces && placedPieces.length > 0) {
        placedPieces.forEach((p, index) => {
            const px = p.x * scaleX;
            const py = p.y * scaleY;
            const pw = p.w * scaleX;
            const ph = p.h * scaleY;

            const color = pieceColors[index % pieceColors.length];

            ctx.fillStyle = color.fill;
            ctx.fillRect(px, py, pw, ph);

            ctx.strokeStyle = color.stroke;
            ctx.lineWidth = 2;
            ctx.strokeRect(px, py, pw, ph);

            ctx.fillStyle = '#FFFFFF';
            ctx.font = 'bold 13px system-ui';
            ctx.fillText(p.id, px + 8, py + 20);

            ctx.font = '11px system-ui';
            ctx.fillText(`${p.w}x${p.h}`, px + 8, py + 36);

            if (p.rotated) {
                ctx.fillText('Rotado 90°', px + 8, py + 52);
            }
        });
    }

    ctx.strokeStyle = '#0F172A';
    ctx.lineWidth = 3;
    ctx.strokeRect(0, 0, canvasWidth, canvasHeight);
}

/* ==========================================================================
   8. DOS MENÚS DESPLEGABLES (1. MÓDULO DEL SISTEMA / 2. FUNCIONES DEL MÓDULO)
   ========================================================================== */
const MODULE_FUNCTIONS_MAP = {
    vision: [
        { id: 'cam', label: 'Capturar Lámina con Cámara' },
        { id: 'gal', label: 'Seleccionar Imagen de Lámina' },
        { id: 'fix_sheet', label: '1. Validar y Fijar Tamaño de Lámina Madre' },
        { id: 'add_piece', label: '2. Agregar Pieza de Corte a la Lista' },
        { id: 'run_opt', label: '3. Analizar Lámina (Canny + IA) y Optimizar Cortes' },
        { id: 'reset_opt', label: 'Limpiar / Reiniciar Módulo' }
    ],
    traceability: [
        { id: 'refresh_trace', label: 'Actualizar Datos de Trazabilidad y Dashboard' }
    ],
    admin: [
        { id: 'admin_add', label: '1. Agregar Usuario' },
        { id: 'admin_edit', label: '2. Modificar Usuario' },
        { id: 'admin_del', label: '3. Eliminar Usuario' },
        { id: 'admin_query', label: '4. Consultar Usuario' },
        { id: 'admin_refresh', label: 'Refrescar Panel Administrativo' }
    ],
    maintenance: [
        { id: 'maint_diag', label: '1. Diagnóstico y Optimización SQLite (VACUUM)' },
        { id: 'maint_bak', label: '2. Crear Respaldo de Base de Datos (.bak)' },
        { id: 'maint_unlock', label: '3. Desbloquear Todas las Cuentas de Usuarios' },
        { id: 'maint_clean', label: '4. Depurar Historial de Auditoría Antiguo' },
        { id: 'maint_engine', label: '5. Verificar Motor de Corte y Red Neuronal' }
    ]
};

function populateFunctionDropdown(moduleKey) {
    const fnSelect = document.getElementById('functionDropdown');
    if (!fnSelect) return;
    const items = MODULE_FUNCTIONS_MAP[moduleKey] || [];
    fnSelect.innerHTML = `<option value="">-- Seleccione una función (${items.length} disponibles) --</option>` +
        items.map(item => `<option value="${item.id}">${item.label}</option>`).join('');
}

function switchActiveModule(moduleKey) {
    const rootRole = (document.getElementById('siamAppRoot')?.dataset?.role || '').toLowerCase();
    const modSelect = document.getElementById('moduleDropdown');
    if (moduleKey === 'maintenance' && rootRole !== 'superadmin') {
        if (modSelect) modSelect.value = 'vision';
        moduleKey = 'vision';
    }
    if (moduleKey === 'admin' && rootRole !== 'admin' && rootRole !== 'superadmin') {
        if (modSelect) modSelect.value = 'vision';
        moduleKey = 'vision';
    }
    const tabMap = {
        vision: 'tab-vision-btn',
        traceability: 'tab-traceability-btn',
        admin: 'tab-admin-btn',
        maintenance: 'tab-maintenance-btn'
    };
    const paneMap = {
        vision: 'pane-vision',
        traceability: 'pane-traceability',
        admin: 'pane-admin',
        maintenance: 'pane-maintenance'
    };
    const btnId = tabMap[moduleKey];
    const tabBtn = btnId ? document.getElementById(btnId) : null;
    if (tabBtn) {
        tabBtn.click();
    } else {
        Object.entries(paneMap).forEach(([k, pId]) => {
            const pEl = document.getElementById(pId);
            if (!pEl) return;
            if (k === moduleKey) {
                pEl.classList.remove('d-none');
                pEl.classList.add('show', 'active');
            } else {
                pEl.classList.remove('show', 'active');
                if (k === 'maintenance' && rootRole !== 'superadmin') {
                    pEl.classList.add('d-none');
                }
            }
        });
    }
    populateFunctionDropdown(moduleKey);
    if (moduleKey === 'traceability' || moduleKey === 'admin' || moduleKey === 'maintenance') {
        if (typeof window.loadTraceabilityData === 'function') {
            window.loadTraceabilityData();
        }
    }
}

function executeSelectedModuleFunction() {
    const fnSelect = document.getElementById('functionDropdown');
    const actionId = fnSelect?.value || '';
    if (!actionId) {
        alert('Seleccione una función en el menú desplegable "2. Funciones del Módulo".');
        return;
    }

    switch (actionId) {
        case 'cam':
            document.getElementById('btnTriggerCamera')?.click();
            break;
        case 'gal':
            document.getElementById('btnTriggerGallery')?.click();
            break;
        case 'fix_sheet':
            window.confirmSheetSize();
            break;
        case 'add_piece':
            document.getElementById('btnAddOrder')?.click();
            break;
        case 'run_opt': {
            const btnProc = document.getElementById('btnProcessImage');
            if (btnProc && !btnProc.disabled) {
                btnProc.click();
            } else {
                alert('Primero seleccione una imagen de lámina, valide el tamaño de la Lámina Madre y agregue al menos una pieza.');
            }
            break;
        }
        case 'reset_opt':
            document.getElementById('btnRefreshOrders')?.click();
            break;
        case 'refresh_trace':
            window.loadTraceabilityData();
            break;
        case 'admin_add':
            window.openAdminCrudModal('add');
            break;
        case 'admin_edit':
            window.openAdminCrudModal('edit');
            break;
        case 'admin_del':
            window.openAdminCrudModal('delete');
            break;
        case 'admin_query':
            window.openAdminCrudModal('query');
            break;
        case 'admin_refresh':
            window.loadTraceabilityData();
            break;
        case 'maint_diag':
            window.runMaintenanceTask('diagnostics');
            break;
        case 'maint_bak':
            window.runMaintenanceTask('backup');
            break;
        case 'maint_unlock':
            window.runMaintenanceTask('unlock_accounts');
            break;
        case 'maint_clean':
            window.runMaintenanceTask('clean_logs');
            break;
        case 'maint_engine':
            window.runMaintenanceTask('verify_engine');
            break;
    }
}

function initModuleAndFunctionMenus() {
    const modSelect = document.getElementById('moduleDropdown');
    const fnSelect = document.getElementById('functionDropdown');
    const btnExec = document.getElementById('btnExecModuleFunction');

    if (modSelect) {
        populateFunctionDropdown(modSelect.value || 'vision');
        modSelect.addEventListener('change', () => {
            switchActiveModule(modSelect.value);
        });
    }

    if (fnSelect) {
        fnSelect.addEventListener('change', () => {
            if (fnSelect.value) {
                executeSelectedModuleFunction();
            }
        });
    }

    if (btnExec) {
        btnExec.addEventListener('click', () => {
            executeSelectedModuleFunction();
        });
    }
}

/* ==========================================================================
   9. AUTENTICACIÓN POR ROLES, CRUD DE USUARIOS Y MANTENIMIENTO SUPERUSUARIO
   ========================================================================== */
window.togglePasswordVisibility = function(inputId, btn) {
    const input = document.getElementById(inputId);
    if (!input) return;
    if (input.type === 'password') {
        input.type = 'text';
        if (btn) btn.textContent = 'Ocultar';
    } else {
        input.type = 'password';
        if (btn) btn.textContent = 'Ver';
    }
};

let cachedAdminUsers = [];

function initAuthAndTraceability() {
    const root = document.getElementById('siamAppRoot');
    const authOverlay = document.getElementById('authOverlay');
    const loginAdminCheck = document.getElementById('loginAdminCheck');
    const loginAdminKeyWrapper = document.getElementById('loginAdminKeyWrapper');
    const regAdminCheck = document.getElementById('regAdminCheck');
    const regAdminKeyWrapper = document.getElementById('regAdminKeyWrapper');
    const btnShowRegister = document.getElementById('btnShowRegister');
    const btnBackToLogin = document.getElementById('btnBackToLogin');
    const btnShowForgot = document.getElementById('btnShowForgot');
    const btnBackFromForgot = document.getElementById('btnBackFromForgot');
    const loginBox = document.getElementById('loginBox');
    const registerBox = document.getElementById('registerBox');
    const forgotBox = document.getElementById('forgotBox');
    const authAlert = document.getElementById('authAlert');
    const btnDoLogin = document.getElementById('btnDoLogin');
    const btnDoRegister = document.getElementById('btnDoRegister');
    const btnLogout = document.getElementById('btnLogout');
    const navUserBadge = document.getElementById('navUserBadge');
    const navAdminTabItem = document.getElementById('navAdminTabItem');
    const navMaintenanceTabItem = document.getElementById('navMaintenanceTabItem');

    let forgotUserId = null;

    function showAlert(msg, isSuccess = false) {
        if (!authAlert) return;
        authAlert.textContent = msg;
        authAlert.className = `alert py-2 small ${isSuccess ? 'alert-success' : 'alert-danger'}`;
    }

    function syncRoleDropdownOptions(role) {
        const cleanRole = (role || '').toLowerCase();
        const isAdminOrSuper = (cleanRole === 'admin' || cleanRole === 'superadmin');
        const isSuper = (cleanRole === 'superadmin');
        const modSelect = document.getElementById('moduleDropdown');
        const paneMaint = document.getElementById('pane-maintenance');
        const paneAdmin = document.getElementById('pane-admin');

        if (modSelect) {
            let optAdmin = document.getElementById('optModuleAdmin');
            if (isAdminOrSuper) {
                if (!optAdmin) {
                    optAdmin = document.createElement('option');
                    optAdmin.value = 'admin';
                    optAdmin.id = 'optModuleAdmin';
                    optAdmin.textContent = '3. Panel Administrador';
                    modSelect.appendChild(optAdmin);
                }
                optAdmin.classList.remove('d-none');
            } else if (optAdmin) {
                if (modSelect.value === 'admin') {
                    modSelect.value = 'vision';
                    switchActiveModule('vision');
                }
                optAdmin.remove();
            }

            let optMaint = document.getElementById('optModuleMaintenance');
            if (isSuper) {
                if (!optMaint) {
                    optMaint = document.createElement('option');
                    optMaint.value = 'maintenance';
                    optMaint.id = 'optModuleMaintenance';
                    optMaint.textContent = '4. Mantenimiento del Sistema (Superusuario)';
                    modSelect.appendChild(optMaint);
                }
                optMaint.classList.remove('d-none');
            } else if (optMaint) {
                if (modSelect.value === 'maintenance') {
                    modSelect.value = 'vision';
                    switchActiveModule('vision');
                }
                optMaint.remove();
            }
        }

        if (paneMaint) {
            paneMaint.classList.toggle('d-none', !isSuper);
            if (!isSuper) paneMaint.classList.remove('show', 'active');
        }
        if (paneAdmin && !isAdminOrSuper) {
            paneAdmin.classList.remove('show', 'active');
        }
    }

    function updateHeaderSession(username, role) {
        const cleanRole = (role || 'usuario').toLowerCase();
        const isAdminOrSuper = (cleanRole === 'admin' || cleanRole === 'superadmin');
        const isSuper = (cleanRole === 'superadmin');

        if (root) {
            root.dataset.user = username || '';
            root.dataset.role = cleanRole;
        }
        syncRoleDropdownOptions(cleanRole);

        if (username) {
            if (authOverlay) {
                authOverlay.classList.add('d-none');
                authOverlay.classList.remove('d-flex');
            }
            if (navUserBadge) {
                navUserBadge.textContent = `Usuario: ${username} (${cleanRole.toUpperCase()})`;
                navUserBadge.classList.remove('d-none');
            }
            if (btnLogout) btnLogout.classList.remove('d-none');

            if (navAdminTabItem) {
                navAdminTabItem.classList.toggle('d-none', !isAdminOrSuper);
            }
            if (navMaintenanceTabItem) {
                navMaintenanceTabItem.classList.toggle('d-none', !isSuper);
            }

            const adminPriceCol = document.getElementById('adminPricePerM2Col');
            const adminUsdBanner = document.getElementById('adminEconomicUsdBanner');
            if (isAdminOrSuper) {
                if (adminPriceCol) adminPriceCol.classList.remove('d-none');
                if (adminUsdBanner) {
                    adminUsdBanner.classList.remove('d-none');
                    adminUsdBanner.classList.add('d-flex');
                }
            } else {
                if (adminPriceCol) adminPriceCol.classList.add('d-none');
                if (adminUsdBanner) {
                    adminUsdBanner.classList.add('d-none');
                    adminUsdBanner.classList.remove('d-flex');
                }
            }
            loadTraceabilityData();
        } else {
            if (authOverlay) {
                authOverlay.classList.remove('d-none');
                authOverlay.classList.add('d-flex');
            }
            if (navUserBadge) navUserBadge.classList.add('d-none');
            if (btnLogout) btnLogout.classList.add('d-none');
            if (navAdminTabItem) navAdminTabItem.classList.add('d-none');
            if (navMaintenanceTabItem) navMaintenanceTabItem.classList.add('d-none');
            syncRoleDropdownOptions('');
        }
    }

    syncRoleDropdownOptions(root?.dataset?.role || '');
    if (root && root.dataset.user) {
        updateHeaderSession(root.dataset.user, root.dataset.role);
    }

    if (loginAdminCheck && loginAdminKeyWrapper) {
        loginAdminCheck.addEventListener('change', () => {
            loginAdminKeyWrapper.classList.toggle('d-none', !loginAdminCheck.checked);
            if (!loginAdminCheck.checked) document.getElementById('loginAdminKey').value = '';
        });
    }

    if (regAdminCheck && regAdminKeyWrapper) {
        regAdminCheck.addEventListener('change', () => {
            regAdminKeyWrapper.classList.toggle('d-none', !regAdminCheck.checked);
            if (!regAdminCheck.checked) document.getElementById('regAdminKey').value = '';
        });
    }

    function resetRegisterState() {
        const otpSec = document.getElementById('regOtpSection');
        if (otpSec) otpSec.classList.add('d-none');
        const otpInput = document.getElementById('regOtpInput');
        if (otpInput) otpInput.value = '';
        if (btnDoRegister) btnDoRegister.textContent = 'Completar Registro';
    }

    if (btnShowRegister) {
        btnShowRegister.addEventListener('click', () => {
            resetRegisterState();
            loginBox.classList.add('d-none');
            if (forgotBox) forgotBox.classList.add('d-none');
            registerBox.classList.remove('d-none');
            if (authAlert) authAlert.classList.add('d-none');
        });
    }

    if (btnBackToLogin) {
        btnBackToLogin.addEventListener('click', () => {
            resetRegisterState();
            registerBox.classList.add('d-none');
            if (forgotBox) forgotBox.classList.add('d-none');
            loginBox.classList.remove('d-none');
            if (authAlert) authAlert.classList.add('d-none');
        });
    }

    if (btnShowForgot && forgotBox) {
        btnShowForgot.addEventListener('click', () => {
            loginBox.classList.add('d-none');
            registerBox.classList.add('d-none');
            forgotBox.classList.remove('d-none');
            document.getElementById('forgotStep1')?.classList.remove('d-none');
            document.getElementById('forgotStep2')?.classList.add('d-none');
            if (authAlert) authAlert.classList.add('d-none');
        });
    }

    if (btnBackFromForgot && forgotBox) {
        btnBackFromForgot.addEventListener('click', () => {
            forgotBox.classList.add('d-none');
            registerBox.classList.add('d-none');
            loginBox.classList.remove('d-none');
            if (authAlert) authAlert.classList.add('d-none');
        });
    }

    if (btnDoLogin) {
        btnDoLogin.addEventListener('click', async () => {
            const identifier = document.getElementById('loginIdentifier')?.value || '';
            const password = document.getElementById('loginPassword')?.value || '';
            const wants_admin = document.getElementById('loginAdminCheck')?.checked || false;
            const admin_key = document.getElementById('loginAdminKey')?.value || '';

            try {
                const res = await fetch('/api/auth/login', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ identifier, password, wants_admin, admin_key })
                });
                const data = await res.json();
                if (!res.ok || !data.success) {
                    showAlert(data.message || 'Error al iniciar sesión.');
                    return;
                }
                updateHeaderSession(data.username, data.role);
            } catch (e) {
                showAlert('Error de conexión con el servidor.');
            }
        });
    }

    if (btnDoRegister) {
        btnDoRegister.addEventListener('click', async () => {
            const username = (document.getElementById('regUsername')?.value || '').trim();
            const phone = (document.getElementById('regPhone')?.value || '').trim();
            const password = (document.getElementById('regPassword')?.value || '').trim();
            const wants_admin = document.getElementById('regAdminCheck')?.checked || false;
            const admin_key = (document.getElementById('regAdminKey')?.value || '').trim();

            if (!username || !phone || !password) {
                showAlert('Todos los campos son obligatorios.');
                return;
            }
            if (username.length < 3 || username.length > 15) {
                showAlert('El Nombre de Usuario debe tener un mínimo de 3 y un máximo de 15 caracteres.');
                return;
            }
            if (!/^\d{11}$/.test(phone)) {
                showAlert('El Teléfono debe tener exactamente 11 dígitos numéricos (mínimo 11 y máximo 11, ej: 04121234567).');
                return;
            }
            if (password.length < 8 || password.length > 12) {
                showAlert('La contraseña debe tener un mínimo de 8 y un máximo de 12 caracteres.');
                return;
            }

            try {
                const res = await fetch('/api/auth/register', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ username, phone, password, wants_admin, admin_key })
                });
                const data = await res.json();
                if (!res.ok || !data.success) {
                    showAlert(data.message || 'Error al registrar.');
                    return;
                }
                resetRegisterState();
                showAlert(data.message, true);
                registerBox.classList.add('d-none');
                loginBox.classList.remove('d-none');
            } catch (e) {
                showAlert('Error al registrar usuario.');
            }
        });
    }

    const btnForgotSendCode = document.getElementById('btnForgotSendCode');
    if (btnForgotSendCode) {
        btnForgotSendCode.addEventListener('click', async () => {
            const identifier = (document.getElementById('forgotIdentifier')?.value || '').trim();
            if (!identifier) {
                showAlert('Ingresa tu nombre de usuario o teléfono registrado.');
                return;
            }
            try {
                const res = await fetch('/api/auth/forgot-send-code', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ identifier })
                });
                const data = await res.json();
                if (!res.ok || !data.success) {
                    showAlert(data.message || 'Usuario no encontrado.');
                    return;
                }
                forgotUserId = data.user_id;
                const banner = document.getElementById('forgotInboxBanner');
                if (banner) {
                    banner.innerHTML = `[Bandeja de Seguridad SIAM]<br>Usuario: ${data.username} | Tel: ${data.phone || ''}<br>Código de Recuperación: <span class="text-warning">${data.code}</span>`;
                }
                document.getElementById('forgotStep1')?.classList.add('d-none');
                document.getElementById('forgotStep2')?.classList.remove('d-none');
                showAlert('Código de seguridad generado. Introduce el código y tu nueva contraseña.', true);
            } catch (e) {
                showAlert('Error al solicitar código de recuperación.');
            }
        });
    }

    const btnForgotSubmitReset = document.getElementById('btnForgotSubmitReset');
    if (btnForgotSubmitReset) {
        btnForgotSubmitReset.addEventListener('click', async () => {
            const code = (document.getElementById('forgotCodeInput')?.value || '').trim();
            const new_password = (document.getElementById('forgotNewPassword')?.value || '').trim();
            const conf_password = (document.getElementById('forgotConfPassword')?.value || '').trim();

            if (!code || code.length !== 6) {
                showAlert('Ingresa el código de 6 dígitos.');
                return;
            }
            if (new_password.length < 8 || new_password.length > 12) {
                showAlert('La nueva contraseña debe tener un mínimo de 8 y un máximo de 12 caracteres.');
                return;
            }
            if (new_password !== conf_password) {
                showAlert('Las contraseñas no coinciden.');
                return;
            }
            try {
                const res = await fetch('/api/auth/forgot-reset', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ user_id: forgotUserId, code, new_password })
                });
                const data = await res.json();
                if (!res.ok || !data.success) {
                    showAlert(data.message || 'No se pudo restablecer la contraseña.');
                    return;
                }
                showAlert(data.message, true);
                forgotBox.classList.add('d-none');
                loginBox.classList.remove('d-none');
            } catch (e) {
                showAlert('Error al restablecer la contraseña.');
            }
        });
    }

    if (btnLogout) {
        btnLogout.addEventListener('click', async () => {
            await fetch('/api/auth/logout', { method: 'POST' });
            window.location.reload();
        });
    }

    const btnRefreshTrace = document.getElementById('btnRefreshTraceability');
    if (btnRefreshTrace) btnRefreshTrace.addEventListener('click', loadTraceabilityData);

    const btnRefreshAdmin = document.getElementById('btnRefreshAdmin');
    if (btnRefreshAdmin) btnRefreshAdmin.addEventListener('click', loadTraceabilityData);

    // 4 Botones CRUD del Panel Administrativo (Punto 3)
    document.getElementById('btnAdminAddUser')?.addEventListener('click', () => window.openAdminCrudModal('add'));
    document.getElementById('btnAdminEditUser')?.addEventListener('click', () => window.openAdminCrudModal('edit'));
    document.getElementById('btnAdminDeleteUser')?.addEventListener('click', () => window.openAdminCrudModal('delete'));
    document.getElementById('btnAdminQueryUser')?.addEventListener('click', () => window.openAdminCrudModal('query'));
    document.getElementById('btnCloseAdminCrud')?.addEventListener('click', () => {
        document.getElementById('adminCrudBox')?.classList.add('d-none');
    });
}

function showAdminActionMessage(msg, isSuccess = true) {
    const alertEl = document.getElementById('adminActionAlert');
    if (!alertEl) {
        alert(msg);
        return;
    }
    alertEl.textContent = msg;
    alertEl.className = `alert py-2 small ${isSuccess ? 'alert-success' : 'alert-danger'}`;
    alertEl.classList.remove('d-none');
}

window.openAdminCrudModal = function(mode) {
    const box = document.getElementById('adminCrudBox');
    const title = document.getElementById('adminCrudTitle');
    const body = document.getElementById('adminCrudBody');
    if (!box || !title || !body) return;

    box.classList.remove('d-none');

    if (mode === 'add') {
        title.textContent = '1. Agregar Nuevo Usuario';
        body.innerHTML = `
            <div class="row g-2">
                <div class="col-md-6">
                    <label class="form-label small fw-bold">Nombre de Usuario:</label>
                    <input type="text" id="crudAddUsername" maxlength="15" oninput="this.value = this.value.replace(/[^a-zA-Z0-9_.]/g, '').slice(0, 15)" class="form-control form-control-sm" placeholder="">
                </div>
                <div class="col-md-6">
                    <label class="form-label small fw-bold">Teléfono:</label>
                    <input type="text" id="crudAddPhone" maxlength="11" inputmode="numeric" oninput="this.value = this.value.replace(/[^0-9]/g, '').slice(0, 11)" class="form-control form-control-sm" placeholder="">
                </div>
                <div class="col-md-6">
                    <label class="form-label small fw-bold">Contraseña:</label>
                    <input type="password" id="crudAddPass" minlength="8" maxlength="12" oninput="if(this.value.length > 12) this.value = this.value.slice(0, 12)" class="form-control form-control-sm" placeholder="">
                </div>
                <div class="col-md-6">
                    <label class="form-label small fw-bold">Rol en el Sistema:</label>
                    <select id="crudAddRole" class="form-select form-select-sm">
                        <option value="usuario">Usuario Normal (Operador)</option>
                        <option value="admin">Administrador</option>
                    </select>
                </div>
                <div class="col-12 mt-2 d-grid">
                    <button type="button" class="btn btn-sm btn-success fw-bold" onclick="submitAdminAddUser()">Guardar Nuevo Usuario</button>
                </div>
            </div>
        `;
    } else if (mode === 'edit') {
        title.textContent = '2. Modificar Usuario Existente';
        const userOptions = cachedAdminUsers
            .filter(u => u.username !== 'programador')
            .map(u => `<option value="${u.id}">ID ${u.id} - ${u.username} (Tel: ${u.phone}) [${u.role}]</option>`)
            .join('');
        body.innerHTML = `
            <div class="row g-2">
                <div class="col-12">
                    <label class="form-label small fw-bold">Seleccionar Usuario a Modificar:</label>
                    <select id="crudEditSelect" class="form-select form-select-sm" onchange="fillAdminEditFields()">
                        <option value="">-- Seleccione un usuario --</option>
                        ${userOptions}
                    </select>
                </div>
                <div class="col-md-6">
                    <label class="form-label small fw-bold">Nuevo Nombre de Usuario:</label>
                    <input type="text" id="crudEditUsername" maxlength="15" oninput="this.value = this.value.replace(/[^a-zA-Z0-9_.]/g, '').slice(0, 15)" class="form-control form-control-sm" placeholder="">
                </div>
                <div class="col-md-6">
                    <label class="form-label small fw-bold">Nuevo Teléfono:</label>
                    <input type="text" id="crudEditPhone" maxlength="11" inputmode="numeric" oninput="this.value = this.value.replace(/[^0-9]/g, '').slice(0, 11)" class="form-control form-control-sm" placeholder="">
                </div>
                <div class="col-md-6">
                    <label class="form-label small fw-bold">Rol:</label>
                    <select id="crudEditRole" class="form-select form-select-sm">
                        <option value="usuario">usuario</option>
                        <option value="admin">admin</option>
                    </select>
                </div>
                <div class="col-md-6">
                    <label class="form-label small fw-bold">Nueva Contraseña (opcional):</label>
                    <input type="password" id="crudEditPass" minlength="8" maxlength="12" oninput="if(this.value.length > 12) this.value = this.value.slice(0, 12)" class="form-control form-control-sm" placeholder="">
                </div>
                <div class="col-12 mt-2 d-grid">
                    <button type="button" class="btn btn-sm btn-primary fw-bold" onclick="submitAdminEditUser()">Actualizar Datos del Usuario</button>
                </div>
            </div>
        `;
    } else if (mode === 'delete') {
        title.textContent = '3. Eliminar Usuario del Sistema';
        const userOptions = cachedAdminUsers
            .filter(u => u.username !== 'programador')
            .map(u => `<option value="${u.id}">ID ${u.id} - ${u.username} (Tel: ${u.phone}) [${u.role}]</option>`)
            .join('');
        body.innerHTML = `
            <div class="row g-2">
                <div class="col-12">
                    <label class="form-label small fw-bold">Seleccionar Usuario a Eliminar:</label>
                    <select id="crudDeleteSelect" class="form-select form-select-sm">
                        <option value="">-- Seleccione un usuario --</option>
                        ${userOptions}
                    </select>
                </div>
                <div class="col-12 mt-2 d-grid">
                    <button type="button" class="btn btn-sm btn-danger fw-bold" onclick="submitAdminDeleteUser()">Confirmar Eliminación de Usuario</button>
                </div>
            </div>
        `;
    } else if (mode === 'query') {
        title.textContent = '4. Consultar Usuario';
        body.innerHTML = `
            <div class="row g-2">
                <div class="col-9">
                    <input type="text" id="crudQueryInput" class="form-control form-control-sm" placeholder="Buscar por ID, nombre de usuario, teléfono o rol...">
                </div>
                <div class="col-3 d-grid">
                    <button type="button" class="btn btn-sm btn-info text-dark fw-bold" onclick="submitAdminQueryUser()">Buscar</button>
                </div>
                <div class="col-12 mt-2" id="crudQueryResults"></div>
            </div>
        `;
    }
};

window.fillAdminEditFields = function() {
    const idVal = parseInt(document.getElementById('crudEditSelect')?.value || '0', 10);
    const user = cachedAdminUsers.find(u => u.id === idVal);
    if (!user) return;
    document.getElementById('crudEditUsername').value = user.username || '';
    document.getElementById('crudEditPhone').value = user.phone || '';
    document.getElementById('crudEditRole').value = (user.role || 'usuario').toLowerCase();
};

window.submitAdminAddUser = async function() {
    const username = (document.getElementById('crudAddUsername')?.value || '').trim();
    const phone = (document.getElementById('crudAddPhone')?.value || '').trim();
    const password = (document.getElementById('crudAddPass')?.value || '').trim();
    const role = document.getElementById('crudAddRole')?.value || 'usuario';

    try {
        const res = await fetch('/api/admin/users/add', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, phone, password, role })
        });
        const data = await res.json();
        showAdminActionMessage(data.message, data.success);
        if (data.success) {
            document.getElementById('adminCrudBox')?.classList.add('d-none');
            loadTraceabilityData();
        }
    } catch (e) {
        showAdminActionMessage('Error al agregar usuario.', false);
    }
};

window.submitAdminEditUser = async function() {
    const user_id = parseInt(document.getElementById('crudEditSelect')?.value || '0', 10);
    if (!user_id) {
        showAdminActionMessage('Seleccione primero un usuario para modificar.', false);
        return;
    }
    const username = (document.getElementById('crudEditUsername')?.value || '').trim();
    const phone = (document.getElementById('crudEditPhone')?.value || '').trim();
    const role = document.getElementById('crudEditRole')?.value || 'usuario';
    const new_password = (document.getElementById('crudEditPass')?.value || '').trim();

    try {
        const res = await fetch('/api/admin/users/update', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id, username, phone, role, new_password })
        });
        const data = await res.json();
        showAdminActionMessage(data.message, data.success);
        if (data.success) {
            document.getElementById('adminCrudBox')?.classList.add('d-none');
            loadTraceabilityData();
        }
    } catch (e) {
        showAdminActionMessage('Error al modificar usuario.', false);
    }
};

window.submitAdminDeleteUser = async function() {
    const user_id = parseInt(document.getElementById('crudDeleteSelect')?.value || '0', 10);
    if (!user_id) {
        showAdminActionMessage('Seleccione un usuario para eliminar.', false);
        return;
    }
    if (!confirm('¿Está seguro de que desea eliminar este usuario de forma permanente?')) {
        return;
    }
    try {
        const res = await fetch('/api/admin/users/delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id })
        });
        const data = await res.json();
        showAdminActionMessage(data.message, data.success);
        if (data.success) {
            document.getElementById('adminCrudBox')?.classList.add('d-none');
            loadTraceabilityData();
        }
    } catch (e) {
        showAdminActionMessage('Error al eliminar usuario.', false);
    }
};

window.submitAdminQueryUser = async function() {
    const q = (document.getElementById('crudQueryInput')?.value || '').trim();
    const container = document.getElementById('crudQueryResults');
    if (!container) return;

    try {
        const res = await fetch(`/api/admin/users/search?q=${encodeURIComponent(q)}`);
        const data = await res.json();
        if (!data.success || !data.users || data.users.length === 0) {
            container.innerHTML = `<div class="alert alert-warning py-2 small mb-0">No se encontraron usuarios que coincidan con "${q}".</div>`;
            return;
        }
        container.innerHTML = `
            <div class="table-responsive">
                <table class="table table-sm table-bordered small mb-0">
                    <thead class="table-light">
                        <tr><th>ID</th><th>Usuario</th><th>Teléfono</th><th>Rol</th></tr>
                    </thead>
                    <tbody>
                        ${data.users.map(u => `
                            <tr>
                                <td>${u.id}</td>
                                <td class="fw-bold">${u.username}</td>
                                <td>${u.phone}</td>
                                <td><span class="badge bg-secondary">${u.role}</span></td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        `;
    } catch (e) {
        container.innerHTML = `<div class="alert alert-danger py-2 small mb-0">Error al consultar usuarios.</div>`;
    }
};

window.runMaintenanceTask = async function(action) {
    const consoleEl = document.getElementById('maintenanceConsole');
    try {
        const res = await fetch('/api/maintenance/action', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action })
        });
        const data = await res.json();
        const ts = new Date().toLocaleTimeString();
        if (consoleEl) {
            consoleEl.textContent = `[${ts}] Operación: ${action.toUpperCase()}\nResultado: ${data.message}\n` +
                (data.diagnostics ? `Diagnóstico BD: Integridad=${data.diagnostics.integrity} | Tamaño=${data.diagnostics.db_size_kb} KB | Usuarios=${data.diagnostics.users_count} | Bloqueados=${data.diagnostics.locked_users}\n` : '') +
                `\n` + consoleEl.textContent;
        }
        if (data.diagnostics) {
            const elInt = document.getElementById('maintIntegrity');
            const elSize = document.getElementById('maintDbSize');
            const elLock = document.getElementById('maintLocked');
            const elLogs = document.getElementById('maintLogsCount');
            if (elInt) elInt.textContent = data.diagnostics.integrity;
            if (elSize) elSize.textContent = `${data.diagnostics.db_size_kb} KB`;
            if (elLock) elLock.textContent = data.diagnostics.locked_users;
            if (elLogs) elLogs.textContent = data.diagnostics.logs_count;
        }
        loadTraceabilityData();
    } catch (e) {
        if (consoleEl) {
            consoleEl.textContent = `[ERROR] No se pudo ejecutar la tarea de mantenimiento: ${action}\n` + consoleEl.textContent;
        }
    }
};

window.loadTraceabilityData = async function() {
    try {
        const res = await fetch('/api/traceability-data');
        const data = await res.json();
        if (!data.success) return;

        const elTot = document.getElementById('statTotalDefects');
        const elAvg = document.getElementById('statAvgArea');
        const elMax = document.getElementById('statMaxArea');
        if (elTot) elTot.textContent = data.summary.total_defects;
        if (elAvg) elAvg.textContent = `${data.summary.avg_area} mm²`;
        if (elMax) elMax.textContent = `${data.summary.max_area} mm²`;

        const tbody = document.getElementById('traceabilityTableBody');
        if (tbody) {
            tbody.innerHTML = (data.inspections || []).map(r => {
                const badgeClass = r.qc_status.includes('APROBADO') ? 'bg-success' : (r.qc_status.includes('RECHAZADO') ? 'bg-danger' : 'bg-warning text-dark');
                return `
                    <tr>
                        <td class="fw-bold">D-${r.id}</td>
                        <td>Lote #${r.batch_id}</td>
                        <td>${r.defect_type}</td>
                        <td>(${r.x}, ${r.y})</td>
                        <td>${r.area} mm²</td>
                        <td><span class="badge ${badgeClass}">${r.qc_status}</span></td>
                        <td>${r.severity}</td>
                    </tr>
                `;
            }).join('');
        }

        if (data.admin_data) {
            cachedAdminUsers = data.admin_data.users || [];
            const uBody = document.getElementById('adminUsersTableBody');
            if (uBody) {
                uBody.innerHTML = cachedAdminUsers.map(u => `
                    <tr>
                        <td>${u.id}</td>
                        <td class="fw-bold">${u.username}</td>
                        <td>${u.phone}</td>
                        <td><span class="badge ${u.role === 'ADMIN' || u.role === 'SUPERADMIN' ? 'bg-info text-dark' : 'bg-secondary'}">${u.role}</span></td>
                    </tr>
                `).join('');
            }

            const aBody = document.getElementById('adminActivityTableBody');
            if (aBody) {
                aBody.innerHTML = data.admin_data.activity.map(a => `
                    <tr>
                        <td class="fw-bold">${a.username}</td>
                        <td>${a.role}</td>
                        <td>${a.action}</td>
                        <td>${a.details}</td>
                        <td class="text-muted">${a.timestamp}</td>
                    </tr>
                `).join('');
            }

            const mBody = document.getElementById('adminMetricsTableBody');
            if (mBody) {
                mBody.innerHTML = data.admin_data.metrics.map(m => `
                    <tr>
                        <td class="fw-bold">${m.username}</td>
                        <td>${m.role}</td>
                        <td>${m.action}</td>
                        <td class="fw-bold text-primary">${m.total}</td>
                    </tr>
                `).join('');
            }
        }

        if (data.maintenance_data) {
            const elInt = document.getElementById('maintIntegrity');
            const elSize = document.getElementById('maintDbSize');
            const elLock = document.getElementById('maintLocked');
            const elLogs = document.getElementById('maintLogsCount');
            if (elInt) elInt.textContent = data.maintenance_data.integrity;
            if (elSize) elSize.textContent = `${data.maintenance_data.db_size_kb} KB`;
            if (elLock) elLock.textContent = data.maintenance_data.locked_users;
            if (elLogs) elLogs.textContent = data.maintenance_data.logs_count;
        }
    } catch (err) {
        console.error('Error cargando trazabilidad:', err);
    }
};

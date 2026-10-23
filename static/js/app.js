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

    // 4. Inicializar Gestor de Camara y Pedidos
    initCameraAndUpload();
    initOrdersManager();
    initFormSubmission();
});

/* ==========================================================================
   1. REGISTRO DEL SERVICE WORKER
   ========================================================================== */
function registerServiceWorker() {
    if ('serviceWorker' in navigator) {
        window.addEventListener('load', () => {
            navigator.serviceWorker.register('/sw.js', { scope: '/' })
                .then((registration) => {
                    console.log('✅ [PWA] Service Worker registrado con éxito en el alcance:', registration.scope);
                })
                .catch((error) => {
                    console.error('❌ [PWA] Error al registrar el Service Worker:', error);
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
        // Prevenir la barra de instalacion por defecto del navegador
        e.preventDefault();
        deferredPrompt = e;
        
        // Mostrar banner personalizado para el operario
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
        console.log('🎉 [PWA] SIAM fue instalada satisfactoriamente en el dispositivo');
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
    const previewContainer = document.getElementById('previewContainer');
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

    function handleFile(file) {
        if (!file) return;
        selectedFile = file;

        // Mostrar previsualización
        const reader = new FileReader();
        reader.onload = (e) => {
            previewImage.src = e.target.result;
            previewImage.classList.remove('d-none');
            previewPlaceholder.classList.add('d-none');
            
            // Info de archivo
            const sizeMb = (file.size / (1024 * 1024)).toFixed(2);
            fileInfoText.innerHTML = `<strong>Captura lista:</strong> ${file.name} (${sizeMb} MB)`;
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
   5. GESTOR DE PEDIDOS DE CORTE (Lista interactiva)
   ========================================================================== */
let cuttingOrders = [
    { id: 'Corte-A1', w: 600, h: 500 },
    { id: 'Corte-A2', w: 500, h: 400 },
    { id: 'Corte-B1', w: 700, h: 450 }
];

function initOrdersManager() {
    renderOrdersTable();

    const btnAddOrder = document.getElementById('btnAddOrder');
    if (btnAddOrder) {
        btnAddOrder.addEventListener('click', () => {
            const wInput = document.getElementById('orderWidth');
            const hInput = document.getElementById('orderHeight');
            const idInput = document.getElementById('orderId');

            const w = parseInt(wInput.value, 10);
            const h = parseInt(hInput.value, 10);
            const id = idInput.value.trim() || `Corte-${cuttingOrders.length + 1}`;

            if (isNaN(w) || isNaN(h) || w <= 0 || h <= 0) {
                alert('Por favor ingrese dimensiones válidas en milímetros (mm).');
                return;
            }

            cuttingOrders.push({ id, w, h });
            renderOrdersTable();

            // Limpiar inputs
            wInput.value = '500';
            hInput.value = '400';
            idInput.value = '';
        });
    }
}

function renderOrdersTable() {
    const tableBody = document.getElementById('ordersTableBody');
    if (!tableBody) return;

    if (cuttingOrders.length === 0) {
        tableBody.innerHTML = `<tr><td colspan="4" class="text-center text-muted py-2">Sin pedidos agregados.</td></tr>`;
        return;
    }

    tableBody.innerHTML = cuttingOrders.map((order, idx) => `
        <tr>
            <td class="fw-bold text-primary">${order.id}</td>
            <td>${order.w} mm</td>
            <td>${order.h} mm</td>
            <td class="text-end">
                <button type="button" class="btn btn-sm btn-outline-danger" onclick="removeOrder(${idx})">
                    <i class="bi bi-trash"></i>
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

        if (cuttingOrders.length === 0) {
            alert('Agregue al menos un pedido de corte a la lista.');
            return;
        }

        // Mostrar spinner de procesamiento en móvil
        if (loadingOverlay) loadingOverlay.style.display = 'flex';

        const formData = new FormData();
        formData.append('image', selectedFile);
        formData.append('orders', JSON.stringify(cuttingOrders));
        
        // Dimensiones de la lámina madre
        const sheetWidth = document.getElementById('sheetWidth')?.value || 2000;
        const sheetHeight = document.getElementById('sheetHeight')?.value || 2000;
        formData.append('sheet_width', sheetWidth);
        formData.append('sheet_height', sheetHeight);

        try {
            const response = await fetch('/api/scan-and-optimize', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (!response.ok || !data.success) {
                throw new Error(data.message || 'Error durante el procesamiento en el servidor.');
            }

            // Renderizar resultados
            renderResults(data);

            // Mostrar seccion de resultados y hacer scroll suave
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
    // 1. Datos de Control de Calidad y Defectos
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
            qcBadge.innerHTML = `<i class="bi bi-check-circle-fill"></i> ESTADO: ${data.qc_status}`;
        } else if (data.qc_status === 'APROBADO CON CONDICIÓN') {
            qcBadge.classList.add('qc-condicion');
            qcBadge.innerHTML = `<i class="bi bi-exclamation-triangle-fill"></i> ESTADO: ${data.qc_status}`;
        } else {
            qcBadge.classList.add('qc-rechazado');
            qcBadge.innerHTML = `<i class="bi bi-x-circle-fill"></i> ESTADO: ${data.qc_status}`;
        }
    }

    if (defectTypeEl) defectTypeEl.textContent = data.defect_type || 'Ninguno';
    if (defectConfidenceEl) defectConfidenceEl.textContent = `${(data.confidence || 0).toFixed(1)}%`;
    if (defectAreaEl) defectAreaEl.textContent = `${(data.defect_area || 0).toFixed(1)} mm²`;
    if (qcRecommendationEl) qcRecommendationEl.textContent = data.recommendation || 'Sin observaciones.';

    // Imagen anotada por OpenCV (si viene en base64)
    if (annotatedImg && data.annotated_image_url) {
        annotatedImg.src = data.annotated_image_url;
        annotatedImg.classList.remove('d-none');
    }

    // 2. Metricas de Rendimiento / Merma
    const kpiEfficiency = document.getElementById('kpiEfficiency');
    const kpiWaste = document.getElementById('kpiWaste');
    const kpiPlaced = document.getElementById('kpiPlaced');
    const kpiUsedArea = document.getElementById('kpiUsedArea');

    if (kpiEfficiency) kpiEfficiency.textContent = `${(data.efficiency_score || 0).toFixed(1)}%`;
    if (kpiWaste) kpiWaste.textContent = `${(data.waste_percentage || 0).toFixed(1)}%`;
    if (kpiPlaced) kpiPlaced.textContent = `${data.placed_count || 0}/${data.requested_count || 0}`;
    if (kpiUsedArea) kpiUsedArea.textContent = `${((data.total_area_used || 0) / 1000000).toFixed(2)} m²`;

    // 3. Dibujar Plano de Corte 2D en el Canvas
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

    // Escala milímetros a píxeles del canvas
    const scaleX = canvasWidth / sheetW;
    const scaleY = canvasHeight / sheetH;

    // Fondo de la Lámina Madre
    ctx.fillStyle = '#E2E8F0';
    ctx.fillRect(0, 0, canvasWidth, canvasHeight);

    // Rejilla de fondo milimétrica (cada 200 mm)
    ctx.strokeStyle = '#CBD5E1';
    ctx.lineWidth = 1;
    for (let x = 0; x <= sheetW; x += 200) {
        ctx.beginPath();
        ctx.moveTo(x * scaleX, 0);
        ctx.lineTo(x * scaleX, canvasHeight);
        ctx.stroke();
    }
    for (let y = 0; y <= sheetH; y += 200) {
        ctx.beginPath();
        ctx.moveTo(0, y * scaleY);
        ctx.lineTo(canvasWidth, y * scaleY);
        ctx.stroke();
    }

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

        // Etiqueta de falla
        ctx.fillStyle = '#991B1B';
        ctx.font = 'bold 12px system-ui';
        ctx.fillText('⚠️ DEFECTO', dx + 4, dy + 16);
    }

    // Paleta de colores para las piezas de corte
    const pieceColors = [
        { fill: 'rgba(2, 132, 199, 0.85)', stroke: '#0369A1' },
        { fill: 'rgba(16, 185, 129, 0.85)', stroke: '#047857' },
        { fill: 'rgba(139, 92, 246, 0.85)', stroke: '#6D28D9' },
        { fill: 'rgba(245, 158, 11, 0.85)', stroke: '#D97706' },
        { fill: 'rgba(236, 72, 153, 0.85)', stroke: '#BE185D' }
    ];

    // Dibujar cada pieza acomodada por el algoritmo Bin Packing
    if (placedPieces && placedPieces.length > 0) {
        placedPieces.forEach((p, index) => {
            const px = p.x * scaleX;
            const py = p.y * scaleY;
            const pw = p.w * scaleX;
            const ph = p.h * scaleY;

            const color = pieceColors[index % pieceColors.length];

            // Relleno de la pieza
            ctx.fillStyle = color.fill;
            ctx.fillRect(px, py, pw, ph);

            // Borde de corte preciso
            ctx.strokeStyle = color.stroke;
            ctx.lineWidth = 2;
            ctx.strokeRect(px, py, pw, ph);

            // Texto identificador de la pieza
            ctx.fillStyle = '#FFFFFF';
            ctx.font = 'bold 13px system-ui';
            ctx.fillText(p.id, px + 8, py + 20);

            // Dimensiones
            ctx.font = '11px system-ui';
            ctx.fillText(`${p.w}x${p.h} mm`, px + 8, py + 36);

            // Indicador de rotación si aplica
            if (p.rotated) {
                ctx.fillText('🔄 Rotado 90°', px + 8, py + 52);
            }
        });
    }

    // Borde exterior de la lámina
    ctx.strokeStyle = '#0F172A';
    ctx.lineWidth = 3;
    ctx.strokeRect(0, 0, canvasWidth, canvasHeight);
}

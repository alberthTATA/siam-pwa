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
    initAuthAndTraceability();
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

    const btnRefreshOrders = document.getElementById('btnRefreshOrders');
    if (btnRefreshOrders) {
        btnRefreshOrders.addEventListener('click', () => {
            cuttingOrders = [];
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
    const sevEl = document.getElementById('resultSeverity');
    if (sevEl) sevEl.textContent = data.severity || 'NINGUNA';
    if (qcRecommendationEl) qcRecommendationEl.textContent = data.recommendation || 'Sin observaciones.';
    const badgeTime = document.getElementById('badgeProcessTime');
    if (badgeTime && data.processing_time_sec !== undefined) {
        badgeTime.textContent = `Algoritmo FFD (${data.processing_time_sec}s < 5s RNF)`;
    }

    // Refrescar tablas de trazabilidad después de procesar
    if (typeof loadTraceabilityData === 'function') {
        loadTraceabilityData();
    }

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
    const usedM2 = (data.total_area_used || 0) / 1000000;
    if (kpiUsedArea) kpiUsedArea.textContent = `${usedM2.toFixed(2)} m²`;

    // Cálculo de ahorro e impacto económico en $ USD
    const priceInput = document.getElementById('pricePerM2');
    const pricePerM2 = priceInput ? (parseFloat(priceInput.value) || 25.0) : 25.0;
    const savedUsd = (usedM2 * pricePerM2).toFixed(2);
    const totalSheetM2 = ((data.sheet_w || 2000) * (data.sheet_h || 2000)) / 1000000;
    const totalSheetUsd = (totalSheetM2 * pricePerM2).toFixed(2);
    const kpiEconomicUsd = document.getElementById('kpiEconomicUsd');
    if (kpiEconomicUsd) {
        kpiEconomicUsd.textContent = `$${savedUsd} USD recuperados (de $${totalSheetUsd} USD costo lámina a $${pricePerM2.toFixed(2)}/m²)`;
    }

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

/* ==========================================================================
   8. AUTENTICACIÓN POR ROLES (CLAVE ESPECIAL ADMIN) Y TRAZABILIDAD BD
   ========================================================================== */
window.togglePasswordVisibility = function(inputId, btn) {
    const input = document.getElementById(inputId);
    if (!input) return;
    if (input.type === 'password') {
        input.type = 'text';
        if (btn) btn.textContent = '🙈';
    } else {
        input.type = 'password';
        if (btn) btn.textContent = '👁️';
    }
};

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

    let pendingRegOtp = null;
    let forgotUserId = null;

    function showAlert(msg, isSuccess = false) {
        if (!authAlert) return;
        authAlert.textContent = msg;
        authAlert.className = `alert py-2 small ${isSuccess ? 'alert-success' : 'alert-danger'}`;
    }

    function updateHeaderSession(username, role) {
        if (username) {
            if (authOverlay) {
                authOverlay.classList.add('d-none');
                authOverlay.classList.remove('d-flex');
            }
            if (navUserBadge) {
                navUserBadge.textContent = `👤 ${username} (${(role || 'usuario').toUpperCase()})`;
                navUserBadge.classList.remove('d-none');
            }
            if (btnLogout) btnLogout.classList.remove('d-none');
            if (navAdminTabItem) {
                if (role === 'admin') navAdminTabItem.classList.remove('d-none');
                else navAdminTabItem.classList.add('d-none');
            }
            const adminPriceCol = document.getElementById('adminPricePerM2Col');
            const adminUsdBanner = document.getElementById('adminEconomicUsdBanner');
            if (role === 'admin') {
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
        }
    }

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
        pendingRegOtp = null;
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
            const email = (document.getElementById('regEmail')?.value || '').trim();
            const phone = (document.getElementById('regPhone')?.value || '').trim();
            const password = (document.getElementById('regPassword')?.value || '').trim();
            const wants_admin = document.getElementById('regAdminCheck')?.checked || false;
            const admin_key = (document.getElementById('regAdminKey')?.value || '').trim();

            if (!username || !email || !phone || !password) {
                showAlert('Todos los campos son obligatorios.');
                return;
            }
            if (username.length < 3) {
                showAlert('El Nombre de Usuario debe tener al menos 3 caracteres.');
                return;
            }
            if (!email.includes('@')) {
                showAlert('El Correo Electrónico debe incluir obligatoriamente el signo @.');
                return;
            }
            if (!/^\d{7,15}$/.test(phone)) {
                showAlert('El Teléfono debe contener solo dígitos numéricos (7 a 15 dígitos).');
                return;
            }
            if (password.length < 8) {
                showAlert('La contraseña debe tener un mínimo de 8 caracteres.');
                return;
            }

            // Paso 1: Generar código OTP en la Bandeja de Seguridad SIAM antes de activar la cuenta
            if (!pendingRegOtp) {
                pendingRegOtp = String(Math.floor(100000 + Math.random() * 900000));
                const otpSec = document.getElementById('regOtpSection');
                const banner = document.getElementById('regInboxBanner');
                if (banner) {
                    banner.innerHTML = `📬 [Bandeja de Entrada SIAM]<br>Código de Activación: <span class="text-warning">${pendingRegOtp}</span>`;
                }
                if (otpSec) otpSec.classList.remove('d-none');
                btnDoRegister.textContent = '✅ Verificar Código y Activar Cuenta';
                showAlert(`Hemos enviado el código de activación a ${email}. Ingrésalo abajo para confirmar.`, true);
                return;
            }

            // Paso 2: Validar el código OTP ingresado
            const enteredOtp = (document.getElementById('regOtpInput')?.value || '').trim();
            if (enteredOtp !== pendingRegOtp) {
                showAlert('El código de verificación de 6 dígitos no coincide.');
                return;
            }

            try {
                const res = await fetch('/api/auth/register', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ username, email, phone, password, wants_admin, admin_key })
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
                showAlert('Ingresa tu usuario o correo electrónico registrado.');
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
                    banner.innerHTML = `📬 [Bandeja de Seguridad SIAM]<br>Cuenta: ${data.email}<br>Código de Recuperación: <span class="text-warning">${data.code}</span>`;
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
}

window.loadTraceabilityData = async function() {
    try {
        const res = await fetch('/api/traceability-data');
        const data = await res.json();
        if (!data.success) return;

        // 1. Actualizar KPIs de Trazabilidad
        const elTot = document.getElementById('statTotalDefects');
        const elAvg = document.getElementById('statAvgArea');
        const elMax = document.getElementById('statMaxArea');
        if (elTot) elTot.textContent = data.summary.total_defects;
        if (elAvg) elAvg.textContent = `${data.summary.avg_area} mm²`;
        if (elMax) elMax.textContent = `${data.summary.max_area} mm²`;

        // 2. Poblar tabla de inspecciones
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

        // 3. Poblar tablas del Panel Administrador (si aplica)
        if (data.admin_data) {
            const uBody = document.getElementById('adminUsersTableBody');
            if (uBody) {
                uBody.innerHTML = data.admin_data.users.map(u => `
                    <tr>
                        <td>${u.id}</td>
                        <td class="fw-bold">${u.username}</td>
                        <td>${u.email}</td>
                        <td>${u.phone}</td>
                        <td><span class="badge ${u.role === 'ADMIN' ? 'bg-info text-dark' : 'bg-secondary'}">${u.role}</span></td>
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
    } catch (err) {
        console.error('Error cargando trazabilidad:', err);
    }
};

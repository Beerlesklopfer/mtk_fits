
if (typeof Object.groupBy !== "function") {
    htmx.trigger(document.body, "htmx:error", {
        error: "Dieser Browser wird nicht unterstützt"
    });
}

document.addEventListener("DOMContentLoaded", function () {

    var objCanvas = document.getElementById("toleranceCanvas");
    var objParentDiv = objCanvas.parentElement;
    objCanvas.width = objParentDiv.offsetWidth;
    objCanvas.height = objParentDiv.offsetWidth / 3;

    const nominal_size = document.getElementById('nominal_size').value;
    const objHoleTolerance = document.getElementById('hole-tolerance');
    const objHoleGrade = document.getElementById('hole-grade');
    const objShaftTolerance = document.getElementById('shaft-tolerance');
    const objShaftGrade = document.getElementById('shaft-grade');

    // setFitSystem('hole');

    function setFitSystem(system) {

        const option = document.createElement('option');
        option.disabled = true;

        if (system === 'hole') {
            // Only shaft editable, hole readonly
            option.value = 'H';
            option.innerHTML = 'H';
            option.selected = true;
            objHoleTolerance.appendChild(option);
            objHoleTolerance.setAttribute('disabled', 'disabled');
            objShaftTolerance.removeAttribute('disabled');

        } else if (system === 'shaft') {
            // Only hole editable, shaft readonly
            option.value = 'h';
            option.innerHTML = 'h';
            option.selected = true;
            objShaftTolerance.appendChild(option);
            objShaftTolerance.setAttribute('disabled', 'disabled');
            objHoleTolerance.removeAttribute('disabled');
        } else if (system === 'combined') {
            // Both editable
            objHoleTolerance.removeAttribute('disabled');
            objHoleGrade.removeAttribute('disabled');
            objShaftTolerance.removeAttribute('disabled');
            objShaftGrade.removeAttribute('disabled');
        } else {
            // Default: all enabled
            objHoleTolerance.removeAttribute('disabled');
            objHoleGrade.removeAttribute('disabled');
            objShaftTolerance.removeAttribute('disabled');
            objShaftGrade.removeAttribute('disabled');
        }

    }

    // Event listener for fit-type-select select
    document.getElementById('fit-type-select').addEventListener('change', function (evt) {
        const value = evt.target.value;

        setFitSystem(value);

    });

    // HTMX-Event-Listener for tabular content
    // document.body.addEventListener('htmx:afterSwap', function(evt) {

    //     // raise htmx error in case shaftChrSelect or shaftNumSelect do not exist or have no options
    //     if (!objHoleTolerance || objHoleTolerance.options.length === 0 || !objShaftTolerance || objShaftTolerance.options.length === 0) 
    //     {

    //         const response = JSON.parse(evt.detail.xhr.response);

    //         htmx.trigger(document.body, "htmx:error", {
    //             error: "HTMX-Elemente nicht gefunden oder keine Optionen verfügbar",
    //             details: response
    //             });

    //         console.error(response);
    //         return;
    //     }
    //     // Verhindern, dass das Event erneut ausgelöst wird, wenn es sich um eine Initialisierung handelt
    //     if (evt.target.dataset.initializing) {
    //         evt.stopImmediatePropagation(); 
    //         return;    
    //     }
    // });

    document.body.addEventListener('htmx:afterRequest', function (evt) {

        // Nur auf JSON-Antworten reagieren
        const xhr = evt.detail.xhr;
        const contentType = xhr.getResponseHeader('Content-Type');
        if (!contentType || !contentType.includes('application/json')) {
            return;
        }

        // JSON-Antwort parsen
        const response = JSON.parse(xhr.response);

        // Nur fortfahren, wenn die Anfrage erfolgreich war
        if (evt.detail.successful) {
            if (response.success) {

               
                const objHole       = response.data.Hole
                const objShaft      = response.data.Shaft
                const objTolerances = response.data.Tolerances  

                // Update select options for #hole-tolerance
                const boreCharSelect = document.getElementById('hole-tolerance');
                if (!boreCharSelect.disabled) {
                    boreCharSelect.setAttribute("data-initializing", "true");
                    boreCharSelect.innerHTML = '';
                    objHole.tolerances.forEach(optValue => {
                        const option = document.createElement('option');
                        option.value = optValue;
                        option.innerHTML = optValue;
                        if (objHole.tolerance === optValue) option.selected = true;
                        boreCharSelect.appendChild(option);
                    });
                    boreCharSelect.removeAttribute("data-initializing");
                }

                // Update select options for #bore_class_number
                const boreNumSelect = document.getElementById('hole-grade');
                boreNumSelect.setAttribute("data-initializing", "true");
                boreNumSelect.innerHTML = '';
                objHole.grades.forEach(optValue => {
                    const option = document.createElement('option');
                    option.value = optValue;
                    option.innerHTML = optValue;
                    if (Number(objHole.grade) === Number(optValue)) {
                        option.selected = true;
                    }
                    boreNumSelect.appendChild(option);
                });
                boreNumSelect.removeAttribute("data-initializing");

                // Update select options for #shaft_class_character
                const shaftCharSelect = document.getElementById('shaft-tolerance');
                if (!shaftCharSelect.disabled) {
                    shaftCharSelect.setAttribute("data-initializing", "true");
                    shaftCharSelect.innerHTML = '';
                    objShaft.tolerances.forEach(optValue => {
                        const option = document.createElement('option');
                        option.value = optValue;
                        option.innerHTML = optValue;
                        if (objShaft.tolerance === optValue) option.selected = true;
                        shaftCharSelect.appendChild(option);
                    });
                    shaftCharSelect.removeAttribute("data-initializing");
                }

                // Update select options for #shaft_class_number
                const shaftNumSelect = document.getElementById('shaft-grade');
                shaftNumSelect.setAttribute("data-initializing", "true");
                shaftNumSelect.innerHTML = '';
                objShaft.grades.forEach(optValue => {
                    const option = document.createElement('option');
                    option.value = optValue;
                    option.innerHTML = optValue;
                    if (Number(objShaft.grade) === Number(optValue) ) option.selected = true;
                    shaftNumSelect.appendChild(option);
                });
                shaftNumSelect.removeAttribute("data-initializing");
                
                // Update select options for #shaft_class_number
                const toleranceSelect = document.getElementById('tolerance-select');
                if (toleranceSelect && Array.isArray(objTolerances)){
                    toleranceSelect.setAttribute("data-initializing", "true");
                    toleranceSelect.innerHTML = '';
                    let selectedValue = toleranceSelect.getAttribute('data-selected') || toleranceSelect.value;
                    objTolerances.forEach(optValue => {
                        const option = document.createElement('option');
                        option.value = optValue.tolerance_value;
                        option.innerHTML = optValue.tolerance_class;
                        if (selectedValue && (selectedValue === String(optValue.tolerance_value) || selectedValue === String(optValue.tolerance_class))) {
                            option.selected = true;
                        }
                        toleranceSelect.appendChild(option);
                    });
                    toleranceSelect.removeAttribute("data-initializing");
                    console.log(objTolerances);
                }

                // Update tolerance values
                document.getElementById('ES').innerText = objHole.values.ES + ' µm';
                document.getElementById('EI').innerText = objHole.values.EI + ' µm';
                document.getElementById('T').innerText = objHole.values.T + ' µm';
                document.getElementById('IT').innerText = objHole.values.IT + ' µm';
                document.getElementById('I' ).innerText = objHole.values.I + ' µm';
                document.getElementById('es').innerText = objShaft.values.es + ' µm';
                document.getElementById('ei').innerText = objShaft.values.ei + ' µm';
                document.getElementById('t').innerText = objShaft.values.t + ' µm';
                document.getElementById('it').innerText = objShaft.values.it + ' µm';
                document.getElementById('i' ).innerText = objShaft.values.i + ' µm';

                const objCanvas = document.getElementById('toleranceCanvas');
                const objCtx = objCanvas.getContext('2d');

                // finally draw canvas
                drawToleranceChart(
                    objCanvas, 
                    objCtx, 
                    objHole.values.ES, 
                    objHole.values.EI,
                    objHole.values.D_max,
                    objHole.values.D_min,
                    boreCharSelect.value + boreNumSelect.value,
                    objShaft.values.es, 
                    objShaft.values.ei, 
                    objShaft.values.d_max,
                    objShaft.values.d_min,
                    shaftCharSelect.value + shaftNumSelect.value,
                    nominal_size
                );
            }
        }
    });

    // Optional: Fehlerbehandlung
    document.body.addEventListener('htmx:error', function (evt) {

        messageText = '';
        messageType = '';
        try {
            if (evt.detail.errorInfo && typeof evt.detail.errorInfo === 'object') {
                let response;
                try {
                    response = JSON.parse(evt.detail.errorInfo.error);
                } catch (e) {
                    response = {};
                }
                const errorMessageDiv = document.getElementById('error-message');
                if (response && typeof response === 'object' && response.message) {
                    messageText = response.message;
                } else if (response && typeof response === 'object' && response.messageType) {
                    messageType = response.messageType;
                } else {
                    messageText = 'Ein unbekannter Fehler ist aufgetreten.';
                    messageType = 'Unspezifizierter Fehler';
                }
                errorMessageDiv.innerHTML = '<h1 style="display:inline; text-align:left; vertical-align:middle;">⚠️</h1> <span style="vertical-align:middle; text-align:center; display:inline-block; width:100%;">' + messageText + '</span>';
                errorMessageDiv.classList.remove('d-none');
                setTimeout(function () {
                    errorMessageDiv.classList.add('d-none');
                    errorMessageDiv.innerHTML = '';
                }, 3000);
                console.error('Antwortfehler:', messageText);
            } else {
                console.error('Keine Antwort im Fehlerfall erhalten.');
            }
        } catch (error) {
            console.error('Antwortfehler:', error);
        }

    });

function drawToleranceChart(objCanvas, objCtx, 
                    hole_es, hole_ei, 
                    hole_dmax, hole_dmin, 
                    hole_tolerance,
                    shaft_es, shaft_ei, 
                    shaft_dmax, shaft_dmin, 
                    shaft_tolerance,
                    nominal_size) {

    // Draw the tolerance chart
        const width = objCanvas.width;
        const height = objCanvas.height;
        const padding = 80;
        const chartWidth = width - 2 * padding;
        const chartHeight = height - 2 * padding;
        const nominalSize = parseFloat(nominal_size);

        // Clear canvas
        objCtx.clearRect(0, 0, width, height);
        
        // Calculate tolerance values
        const holeData = {
            maxSize: hole_dmax,
            minSize: hole_dmin
        };

        const shaftData = {
            maxSize: shaft_dmax,
            minSize: shaft_dmin
        };
        
        // Determine min and max values for scaling
        const allValues = [
            hole_dmax, hole_dmin,
            shaft_dmax, shaft_dmin,
            nominal_size
        ];

        const maxValue = Math.max(...allValues) * 1.05;
        const minValue = Math.min(...allValues) * 0.95;
        const valueRange = maxValue - minValue;

        // Calculate scaling factors
        const scale = chartHeight / valueRange;
        
        // Function to calculate Y position from size value
        const getYPos = (value) => {
            return height - padding - (value - minValue) * scale;
        };
        
        // Draw axes
        objCtx.beginPath();
        objCtx.moveTo(padding, padding);
        objCtx.lineTo(padding, height - padding);
        objCtx.lineTo(width - padding, height - padding);
        objCtx.strokeStyle = '#2c3e50';
        objCtx.lineWidth = 2;
        objCtx.stroke();
        
        // Draw axis labels
        objCtx.font = '14px Arial';
        objCtx.fillStyle = '#2c3e50';
        objCtx.textAlign = 'center';
        objCtx.textBaseline = 'middle';
        
        // X-axis label
        objCtx.fillText('Toleranzzonen', width / 2, height - 20);
        
        // Y-axis label
        objCtx.save();
        objCtx.translate(20, height / 2);
        objCtx.rotate(-Math.PI / 2);
        objCtx.fillText('Maß (mm)', 0, 0);
        objCtx.restore();
        
        // Draw grid lines and labels
        objCtx.textAlign = 'right';
        objCtx.textBaseline = 'middle';
        const steps = 5;
        for (let i = 0; i <= steps; i++) {
            const value = minValue + (i / steps) * valueRange;
            const y = getYPos(value);
            // Grid line
            objCtx.beginPath();
            objCtx.moveTo(padding, y);
            objCtx.lineTo(width - padding, y);
            objCtx.strokeStyle = '#ecf0f1';
            objCtx.lineWidth = 1;
            objCtx.stroke();
            
            // Label
            objCtx.fillStyle = '#7f8c8d';
            objCtx.fillText(value.toFixed(2), padding - 10, y);
        }
        
        // Draw tolerance zones
        const holeZoneTop = getYPos(holeData.maxSize);
        const holeZoneBottom = getYPos(holeData.minSize);
        const shaftZoneTop = getYPos(shaftData.maxSize);
        const shaftZoneBottom = getYPos(shaftData.minSize);
        
        // Draw hole tolerance zone
        objCtx.fillStyle = 'rgba(231, 76, 60, 0.2)';
        objCtx.fillRect(padding + 50, holeZoneTop, 150, holeZoneBottom - holeZoneTop);
        objCtx.strokeStyle = '#e74c3c';
        objCtx.lineWidth = 2;
        objCtx.strokeRect(padding + 50, holeZoneTop, 150, holeZoneBottom - holeZoneTop);
        
        // Draw shaft tolerance zone
        objCtx.fillStyle = 'rgba(52, 152, 219, 0.2)';
        objCtx.fillRect(padding + 250, shaftZoneTop, 150, shaftZoneBottom - shaftZoneTop);
        objCtx.strokeStyle = '#3498db';
        objCtx.lineWidth = 2;
        objCtx.strokeRect(padding + 250, shaftZoneTop, 150, shaftZoneBottom - shaftZoneTop);
        
        // Draw nominal size line
        const nominalY = getYPos(nominalSize);
        objCtx.beginPath();
        objCtx.moveTo(padding, nominalY);
        objCtx.lineTo(width - padding, nominalY);
        objCtx.setLineDash([1, 20, 1]);
        objCtx.strokeStyle = '#9b59b6';
        objCtx.lineWidth = 2;
        objCtx.stroke();
        objCtx.setLineDash([]);
        
        // Draw labels for tolerance zones
        objCtx.font = 'bold 16px Arial';
        objCtx.textAlign = 'center';
        
        // Hole label
        objCtx.fillStyle = '#e74c3c';
        objCtx.fillText(`Bohrung: ${hole_tolerance}`, padding + 125, holeZoneTop - 20);
        objCtx.fillText(`Ø ${holeData.maxSize}`, padding + 125, holeZoneTop - 5);
        objCtx.fillText(`Ø ${holeData.minSize}`, padding + 125, holeZoneBottom + 15);
        
        // Shaft label
        objCtx.fillStyle = '#3498db';
        objCtx.fillText(`Welle: ${shaft_tolerance}`, padding + 325, shaftZoneTop - 20);
        objCtx.fillText(`Ø ${shaftData.maxSize}`, padding + 325, shaftZoneTop - 5);
        objCtx.fillText(`Ø ${shaftData.minSize}`, padding + 325, shaftZoneBottom + 15);
        
        // Draw nominal size label
        objCtx.fillStyle = '#9b59b6';
        objCtx.fillText(`Nennmaß: Ø ${nominalSize}`, width - 150, nominalY - 15);
        
        // Draw tolerance symbols
        objCtx.font = '20px Arial';
        objCtx.fillStyle = '#2c3e50';
        objCtx.fillText("↥", padding + 125, holeZoneTop - 40);
        objCtx.fillText("↧", padding + 125, holeZoneBottom + 35);
        objCtx.fillText("↥", padding + 325, shaftZoneTop - 40);
        objCtx.fillText("↧", padding + 325, shaftZoneBottom + 35);
        
        // Draw comparison diagram
        const comparisonX = padding + 500;
        const comparisonWidth = 150;
        
        // Draw hole in comparison
/*        objCtx.beginPath();
        objCtx.arc(comparisonX, nominalY, nominalSize/2, 0, Math.PI * 2);
        objCtx.strokeStyle = '#e74c3c';
        objCtx.lineWidth = 3;
        objCtx.stroke();
        
        // Draw shaft in comparison
        objCtx.beginPath();
        objCtx.arc(comparisonX, nominalY, nominalSize/2 - 5, 0, Math.PI * 2);
        objCtx.strokeStyle = '#3498db';
        objCtx.lineWidth = 3;
        objCtx.stroke(); */
        
        // Draw clearance
        const clearance = holeData.minSize - shaftData.maxSize;
        if (clearance > 0) {
            objCtx.beginPath();
            objCtx.arc(comparisonX, nominalY, nominalSize/2 - 2.5, 0, Math.PI * 2);
            objCtx.setLineDash([2, 2]);
            objCtx.strokeStyle = '#2ecc71';
            objCtx.lineWidth = 1;
            objCtx.stroke();
            objCtx.setLineDash([]);
            
            // Draw clearance indicator
            objCtx.beginPath();
            objCtx.moveTo(comparisonX + nominalSize/2 + 5, nominalY);
            objCtx.lineTo(comparisonX + nominalSize/2 + 20, nominalY);
            objCtx.strokeStyle = '#2c3e50';
            objCtx.lineWidth = 1;
            objCtx.stroke();
            
            objCtx.beginPath();
            objCtx.moveTo(comparisonX + nominalSize/2 + 5, nominalY - 10);
            objCtx.lineTo(comparisonX + nominalSize/2 + 5, nominalY + 10);
            objCtx.stroke();
            
            objCtx.beginPath();
            objCtx.moveTo(comparisonX + nominalSize/2 + 20, nominalY - 10);
            objCtx.lineTo(comparisonX + nominalSize/2 + 20, nominalY + 10);
            objCtx.stroke();
            
            objCtx.font = '12px Arial';
            objCtx.fillStyle = '#2c3e50';
            objCtx.fillText(`Spiel: ${clearance}mm`, comparisonX + nominalSize/2 + 40, nominalY);
        }
        
    }

});

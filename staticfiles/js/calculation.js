
if (typeof Object.groupBy !== "function") {
    htmx.trigger(document.body, "htmx:error", {
        error: "Dieser Browser wird nicht unterstützt"
    });
}

document.addEventListener("DOMContentLoaded", function () {

    // var objCanvas = document.getElementById("toleranceCanvas");
    // var objParentDiv = objCanvas.parentElement;
    // objCanvas.width = objParentDiv.offsetWidth;
    // objCanvas.height = objParentDiv.offsetWidth / 3;

    const htmlBoreToleranceById   = document.getElementById('bore-tolerance');
    const htmlBoreGradeById       = document.getElementById('bore-grade');
    const htmlShaftToleranceById  = document.getElementById('shaft-tolerance');
    const htmlShaftGradeById      = document.getElementById('shaft-grade');
    const htmlToleranceSelectById = document.getElementById('tolerance-select');

    // Function to enable/disable tolerance select based on checkbox
    // function use_286_2_tabellular(isChecked=true) {
    //     if (isChecked) {
    //         htmlToleranceSelectById.setAttribute('disabled', 'disabled');
    //         htmlBoreGradeById.removeAttribute('disabled');
    //         htmlShaftGradeById.removeAttribute('disabled');
    //     } else {
    //         htmlBoreGradeById.setAttribute('disabled', 'disabled');
    //         htmlShaftGradeById.setAttribute('disabled', 'disabled');
    //         htmlToleranceSelectById.removeAttribute('disabled');
    //     }
    // }
    
    // Store references to the select elements
    function populateSelect(htmlSelectById, objResponseData) {
        htmlSelectById.setAttribute("data-initializing", "true");
        const first_option = document.createElement('option');
        first_option.innerHTML = 'Bitte wählen';
        first_option.disabled = true;
        first_option.selected = true;
console.log(`Populating select`, htmlSelectById.id, objResponseData);
        // Clear existing options
        htmlSelectById.innerHTML = '';
        htmlSelectById.appendChild(first_option);
        // Add new options from response data
        objResponseData.forEach(Data => {
            // Create and append the options
            const option = document.createElement('option');
            option.value = Data.tolerance_value;
            option.innerHTML = Data.tolerance_class;
            if (Number(Data.tolerance_value) === Number(Data.tolerance_selected) 
                || String(Data.tolerance_class) === String(Data.tolerance_selected)) {
                    option.selected = true;
                    option.setAttribute('data-selected', true);
                    // console.log(`Populating select`, Data.tolerance_value, Data.tolerance_class, Data.tolerance_selected);
            }
            htmlSelectById.appendChild(option);
        });
        htmlSelectById.removeAttribute("data-initializing");
    }

    function setFitSystem(system) {

        const option = document.createElement('option');
        option.disabled = true;

        if (system === 'hole') {
            // Only bore editable, shaft readonly
            htmlBoreToleranceById.value = 'H';
            htmlBoreToleranceById.dispatchEvent(new Event('change', { bubbles: true }));            
            htmlBoreToleranceById.setAttribute('disabled', 'disabled');
            htmlShaftToleranceById.removeAttribute('disabled');

        } else if (system === 'shaft') {
            // Only hole editable, shaft readonly
            htmlShaftToleranceById.value = 'h';
            htmlShaftToleranceById.dispatchEvent(new Event('change', { bubbles: true }));            
            htmlShaftToleranceById.setAttribute('disabled', 'disabled');
            htmlBoreToleranceById.removeAttribute('disabled');
        } else if (system === 'combined') {
            // Both editable
            htmlBoreToleranceById.removeAttribute('disabled');
            htmlBoreGradeById.removeAttribute('disabled');
            htmlShaftToleranceById.removeAttribute('disabled');
            objShaftGrade.removeAttribute('disabled');
        } else {
            // Default: all enabled
            htmlBoreToleranceById.removeAttribute('disabled');
            htmlBoreGradeById.removeAttribute('disabled');
            htmlShaftToleranceById.removeAttribute('disabled');
            objShaftGrade.removeAttribute('disabled');
        }

    }
    // Event listener for nominal size input
    document.addEventListener("keydown", function (evt) {
        const nominalSizeInput = document.getElementById('nominal_size');
        if (!nominalSizeInput) return;
        let value = parseFloat(nominalSizeInput.value) || 0;
        if (evt.key === '+') {
            nominalSizeInput.value = value + 1;
            nominalSizeInput.dispatchEvent(new Event('change'));
        } else if (evt.key === '-') {
            if (value > 1) {
                nominalSizeInput.value = value - 1;
                nominalSizeInput.dispatchEvent(new Event('change'));
            }
        }
    });

    // Event listener for fit-type-select select
    document.getElementById('fit-type-select').addEventListener('change', function (evt) {
        const value = evt.target.value;

        setFitSystem(value);

    });

    // Event listener for use_iso_286_2 checkbox
    // document.getElementById('use_iso_286_2').addEventListener('change', function (evt) {
    //         use_286_2_tabellular(evt.target.checked);   
    //         setFitSystem(document.getElementById('fit-type-select').value);
    //         // evt.target.setAttribute('data-initializing', 'true');
    //         // evt.target.dispatchEvent(new Event('change', { bubbles: true }));
    //         // evt.target.removeAttribute('data-initializing');
    // });
    
    // Initial setup based on current selection
    document.body.addEventListener('htmx:afterRequest', function (evt) {

        // determine which element triggered the request
        const triggeringElement = evt.target;

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
            if (response.success || response.messageType === 'Hint') {

                // Initial setup based on checkbox state
                // use_286_2_tabellular(document.getElementById('use_iso_286_2').checked);
               
                // if (response.data.Tolerance && Array.isArray(response.data.Tolerance.grades)) {

                //     const { grades, values, selected_tolerance } = response.data.Tolerance;
                //     populateSelect(
                //         htmlToleranceSelectById,
                //         grades.map((grade, index) => ({
                //             tolerance_class: grade,
                //             tolerance_value: values[index],
                //             tolerance_selected: selected_tolerance,
                //         }))
                //     );
                // }
                
                if (response.data.Bore && Array.isArray(response.data.Bore.tolerances)) {
                    populateSelect(htmlBoreToleranceById,
                         response.data.Bore.tolerances.map((tolerance, index) => ({
                             tolerance_class: tolerance,
                             tolerance_value: tolerance,
                             tolerance_selected: response.data.Bore.selected_tolerance,
                         }))
                    );
                }

                // if grade has been selected, set it
                if (response.data.Bore && Array.isArray(response.data.Bore.grades)) {
                    populateSelect(htmlBoreGradeById, 
                        response.data.Bore.grades.map((grade, index) => ({
                            tolerance_class: grade,
                            tolerance_value: grade,
                            tolerance_selected: response.data.Bore.selected_grade,
                        }))
                    );
                } else {
                    htmlBoreGradeById.innerHTML.disabled = 'disabled';
                }

                if (response.data.Shaft && Array.isArray(response.data.Shaft.tolerances)) {
                    populateSelect(htmlShaftToleranceById,
                        response.data.Shaft.tolerances.map((tolerance, index) => ({
                            tolerance_class: tolerance,
                            tolerance_value: tolerance,
                            tolerance_selected: response.data.Shaft.selected_tolerance,
                        }))
                    );
                }

                // if grade has been selected, set it
                if (response.data.Shaft && Array.isArray(response.data.Shaft.grades)) {
                    populateSelect(htmlShaftGradeById,
                        response.data.Shaft.grades.map((grade, index) => ({
                            tolerance_class: grade,
                            tolerance_value: grade,
                            tolerance_selected: response.data.Shaft.selected_grade,
                        }))
                    );
                } else {
                    htmlShaftGradeById.innerHTML.disabled = 'disabled';
                }

                if (response.data.Tolerance !== null) {
                    // document.getElementById('IT').innerText = String(response.data.Tolerance.selected_tolerance) + ' µm';
                    // document.getElementById('it').innerText = String(response.data.Tolerance.selected_tolerance) + ' µm';
                    document.getElementById('s-min').innerText = response.data.Tolerance.s_min.toFixed(3) + ' µm';
                    document.getElementById('s-max').innerText = response.data.Tolerance.s_max.toFixed(3) + ' µm';
                    document.getElementById('fit-type').innerText = response.data.Tolerance['fit-type'] === 'clearance' ? 'Spielpassung' : response.data.Tolerance['fit-type'] === 'interference' ? 'Übermaßpassung' : 'Übergangspassung';
                    document.getElementById('fit-system').innerText = document.getElementById('fit-type-select').options[document.getElementById('fit-type-select').selectedIndex].text;
                } else {
                    // document.getElementById('IT').innerText = '--  µm';
                    // document.getElementById('it').innerText = '--  µm';
                }


                // Wenn Bohrungsdaten vorhanden, dann darstellen
                if (response.data.Bore.results !== null) {
                    const objBore       = response.data.Bore
                    document.getElementById('ES').innerText = objBore.results.ES + ' µm';
                    document.getElementById('EI').innerText = objBore.results.EI + ' µm';
                    document.getElementById('T').innerText = objBore.results.T + ' µm';
                    document.getElementById('ULS').innerText = objBore.results.D_max.toFixed(3) + ' mm';
                    document.getElementById('LLS').innerText = objBore.results.D_min.toFixed(3) + ' mm';
                } else {
                    document.getElementById('ES').innerText = '--  µm';
                    document.getElementById('EI').innerText = '--  µm';
                    document.getElementById('T').innerText = '--  µm';
                    document.getElementById('ULS').innerText = '--  mm';
                    document.getElementById('LLS').innerText = '--  mm';
                }

                // Wenn Wellendaten vorhanden, dann darstellen
                if (response.data.Shaft.results !== null) {
                    const objShaft      = response.data.Shaft
                    document.getElementById('es').innerText = objShaft.results.es + ' µm';
                    document.getElementById('ei').innerText = objShaft.results.ei + ' µm';
                    document.getElementById('t').innerText = objShaft.results.t + ' µm';
                    // document.getElementById('it').innerText = objShaft.results.it + ' µm';
                    document.getElementById('uls').innerText = objShaft.results.d_max.toFixed(3) + ' mm';
                    document.getElementById('lls').innerText = objShaft.results.d_min.toFixed(3) + ' mm';
                    // console.log('Shaft Results:', objShaft.results);
                } else {
                    document.getElementById('es').innerText = '--  µm';
                    document.getElementById('ei').innerText = '--  µm';
                    document.getElementById('t').innerText = '--  µm';
                    // document.getElementById('it').innerText = '--  µm';
                    document.getElementById('uls').innerText = '--  mm';
                    document.getElementById('lls').innerText = '--  mm';
                }

                console.log('Drawing Data:', response.data.Drawing);
                if (response.data.Drawing.image !== null) {
                    const objDrawing = response.data.Drawing;
                    document.getElementById('drawing').src = objDrawing.image;
                    document.getElementById('drawing').alt = objDrawing.alt;
                    document.getElementById('drawing').alt = 'Technische Zeichnung der Passung';
                    document.getElementById('drawing').style.display = 'block';
                } else {
                    document.getElementById('drawing').src = '';
                    document.getElementById('drawing').alt = 'Keine Zeichnung verfügbar';
                    document.getElementById('drawing').style.display = 'none';
                }


                } // Ende if response.success

            // Erst nach einer erfolgreichen Anfrage das Diagramm zeichnen
            if( response.success) {
                // const objCanvas = document.getElementById('toleranceCanvas');
                // const objCtx = objCanvas.getContext('2d');
                const objBore       = response.data.Bore
                const objShaft      = response.data.Shaft
                const objTolerance  = response.data.Tolerances

                // clear canvas
                // objCtx.clearRect(0, 0, objCanvas.width, objCanvas.height);

                // finally draw canvas
                // drawToleranceChart(
                //     objCanvas, objCtx, 
                //     objBore.values.ES, objBore.values.EI,
                //     objBore, objShaft, objTolerance
                // );                
            }
        }
    });

    // Fehlerbehandlung optimiert
    document.body.addEventListener('htmx:error', function (evt) {
        const errorMessageDiv = document.getElementById('error-message');
        let messageText = 'Ein unbekannter Fehler ist aufgetreten.';
        if (evt.detail.errorInfo && typeof evt.detail.errorInfo === 'object') {
            let response;
            try {
                response = JSON.parse(evt.detail.errorInfo.error);
            } catch (e) {
                response = {};
            }
            if (response && typeof response === 'object') {
                if (response.message) {
                    messageText = response.message;
                } else if (response.messageType) {
                    messageText = response.messageType;
                }
            }
        }
        if (errorMessageDiv) {
            errorMessageDiv.innerHTML = '<i class="fa fa-exclamation-triangle" style="display:inline; text-align:left; vertical-align:middle;"></i> <span style="vertical-align:middle; text-align:center; display:inline-block; width:100%;">' + messageText + '</span>';
            errorMessageDiv.classList.remove('d-none');
            setTimeout(function () {
                errorMessageDiv.classList.add('d-none');
                errorMessageDiv.innerHTML = '';
            }, 3000);
        }
        console.error('Antwortfehler:', messageText);
    });

    // event listener for htmx:info instead of error
    document.body.addEventListener('htmx:info', function (evt) {
        const infoMessageDiv = document.getElementById('info-message');
        infoMessageDiv.innerHTML = '<i class="fa fa-info-circle" style="display:inline; text-align:left; vertical-align:middle;"></i> <span style="vertical-align:middle; text-align:center; display:inline-block; width:100%;">' + evt.detail.info + '</span>';
        infoMessageDiv.classList.remove('d-none');
        setTimeout(function () {
            infoMessageDiv.classList.add('d-none');
            infoMessageDiv.innerHTML = '';
        }, 1500);
    });

    // event listener for window resize to adjust canvas size
    window.addEventListener('resize', function () {
        objCanvas.width = objParentDiv.offsetWidth;
    });

    // Function to draw the tolerance chart
    function drawToleranceChart(objCanvas, objCtx, 
                        hole_es, hole_ei, 
                        bore_dmax, bore_dmin,        // 
                        hole_tolerance,              // e.g. H7
                        shaft_es, shaft_ei, 
                        shaft_dmax, shaft_dmin, 
                        shaft_tolerance,
                        nominal_size) {

    console.log('All Values:', nominal_size);

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
        maxSize: bore_dmax,
        minSize: bore_dmin
    };

    const shaftData = {
        maxSize: shaft_dmax,
        minSize: shaft_dmin
    };
        
    // Determine min and max values for scaling
    const allValues = [
        bore_dmax, bore_dmin,
        shaft_dmax, shaft_dmin,
        nominalSize
    ];
    

    // Use nominalSize as the reference and pad the range symmetrically
    const toleranceMax = Math.max(bore_dmax, shaft_dmax, nominalSize);
    const toleranceMin = Math.min(bore_dmin, shaft_dmin, nominalSize);
    const paddingValue = Math.max(Math.abs(toleranceMax - nominalSize), Math.abs(nominalSize - toleranceMin)) * 1.1;
    const maxValue = nominalSize + paddingValue;
    const minValue = nominalSize - paddingValue;
    const valueRange = maxValue - minValue;

    // Calculate scaling factors
    const scale = chartHeight / valueRange;
        
    // Function to calculate Y position from size value
    const getYPos = (value) => {
        return height - padding - (value - minValue) * scale;
    };
     
    // Draw background
    objCtx.fillStyle = '#ffffffff';
    objCtx.fillRect(0, 0, width, height);

    // Draw axes
    objCtx.beginPath();
    objCtx.moveTo(padding, padding);
    objCtx.lineTo(padding, height - padding);
    objCtx.lineTo(width - padding, height - padding);
    objCtx.strokeStyle = '#e50043';
    objCtx.lineWidth = 2;
    objCtx.stroke();
        
    // Draw axis labels
    objCtx.font = '14px Arial';
    objCtx.fillStyle = '#4d4d4d';
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
    // objCtx.translate(20, height / 2);
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
        objCtx.fillStyle = '#4d4d4d';
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
        // console.log(`Nominal Y: ${nominalY} for nominal size ${nominalSize}`);
        objCtx.beginPath();
        objCtx.moveTo(padding, nominalY);
        objCtx.lineTo(width - padding, nominalY);
        objCtx.setLineDash([1, 20, 1]);
        objCtx.strokeStyle = '#4d4d4d';
        objCtx.lineWidth = 2;
        objCtx.stroke();
        objCtx.setLineDash([]);
        
        // Draw labels for tolerance zones
        objCtx.font = 'bold 16px Arial';
        objCtx.textAlign = 'center';
        
        // Bore label
        objCtx.fillStyle = '#38914eff';
        objCtx.fillText(`Bohrung: ${hole_tolerance}`, padding + 125, holeZoneTop - 20);
        objCtx.fillText(`Ø ${holeData.maxSize}`, padding + 125, holeZoneTop - 5);
        objCtx.fillText(`Ø ${holeData.minSize}`, padding + 125, holeZoneBottom + 15);
        
        // Shaft label
        objCtx.fillStyle = '#cbc80aff';
        objCtx.fillText(`Welle: ${shaft_tolerance}`, padding + 325, shaftZoneTop - 20);
        objCtx.fillText(`Ø ${shaftData.maxSize}`, padding + 325, shaftZoneTop - 5);
        objCtx.fillText(`Ø ${shaftData.minSize}`, padding + 325, shaftZoneBottom + 15);
        
        // Draw nominal size label
        objCtx.fillStyle = '#e50043';
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
        objCtx.beginPath();
        objCtx.arc(comparisonX, nominalY, nominalSize/2, 0, Math.PI * 2);
        objCtx.strokeStyle = '#e74c3c';
        objCtx.lineWidth = 3;
        objCtx.stroke();
        
        // Draw shaft in comparison
        objCtx.beginPath();
        objCtx.arc(comparisonX, nominalY, nominalSize/2 - 5, 0, Math.PI * 2);
        objCtx.strokeStyle = '#3498db';
        objCtx.lineWidth = 3;
        objCtx.stroke(); 
        
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

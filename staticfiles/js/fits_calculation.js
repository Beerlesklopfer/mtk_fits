
if (typeof Object.groupBy !== "function") {
    htmx.trigger(document.body, "htmx:error", {
        error: "Dieser Browser wird nicht unterstützt"
    });
}

document.addEventListener("DOMContentLoaded", function () {
    // Get references to HTML elements
    const htmlFitSystemSelectById  = document.getElementById('fit-system-select');
    const htmlNominalSizeById      = document.getElementById('nominal_size');
    const htmlBoreToleranceById    = document.getElementById('bore-tolerance');
    const htmlBoreGradeById        = document.getElementById('bore-grade');
    const htmlShaftToleranceById   = document.getElementById('shaft-tolerance');
    const htmlShaftGradeById       = document.getElementById('shaft-grade');

    try {

        // Store references to the select elements
        function populateSelect(htmlSelectById, objResponseData) {
            htmlSelectById.setAttribute("data-initializing", "true");
            const first_option = document.createElement('option');
            first_option.innerHTML = 'Bitte wählen';
            first_option.disabled = true;
            first_option.selected = true;
// console.debug(`Populating select`, htmlSelectById.id, objResponseData);
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
                document.getElementById('fit-type-system-msg').innerText = 'Einheitsbohrung';

            } else if (system === 'shaft') {
                // Only hole editable, shaft readonly
                htmlShaftToleranceById.value = 'h';
                htmlShaftToleranceById.dispatchEvent(new Event('change', { bubbles: true }));
                htmlShaftToleranceById.setAttribute('disabled', 'disabled');
                htmlBoreToleranceById.removeAttribute('disabled');
                document.getElementById('fit-type-system-msg').innerText = 'Einheitswelle';

            } else if (system === 'combined') {
                // Both editable
                htmlBoreToleranceById.removeAttribute('disabled');
                htmlBoreGradeById.removeAttribute('disabled');
                htmlShaftToleranceById.removeAttribute('disabled');
                htmlShaftGradeById.removeAttribute('disabled');
                document.getElementById('fit-type-system-msg').innerText = 'Kombinierte Passung';

            } else {
                // Default: all enabled
                htmlBoreToleranceById.removeAttribute('disabled');
                htmlBoreGradeById.removeAttribute('disabled');
                htmlShaftToleranceById.removeAttribute('disabled');
                htmlShaftGradeById.removeAttribute('disabled');
            }

            // Trigger change events to update the form
            // htmlBoreToleranceById.dispatchEvent(new Event('', { bubbles: true }));
            // htmlShaftToleranceById.dispatchEvent(new Event('load', { bubbles: true }));
        }

        // Helper function to show notifications
        function showNotification(type, message) {

            const errorMessageDiv = document.getElementById('error-message');
            // errorMessageDiv.innerHTML = '<i class="fa fa-exclamation-triangle" style="display:inline; text-align:left; vertical-align:middle;"></i> <span style="vertical-align:middle; text-align:center; display:inline-block; width:100%;">' + message + '</span>';
            errorMessageDiv.classList.remove('d-none');

            errorMessageDiv.className = `notification ${type}`;
            errorMessageDiv.textContent = message;
            errorMessageDiv.style.cssText = `
                position: fixed;
                top: 20px;
                right: 20px;
                padding: 15px;
                border-radius: 5px;
                color: white;
                z-index: 1000;
                ${type === 'error' ? 'background: #f44336;' : 'background: #4CAF50;'}
            `;
                        
            setTimeout(function () {
                errorMessageDiv.classList.add('d-none');
                errorMessageDiv.innerHTML = '';
            }, 3000);

            if (type === 'error') {
                console.error('Error Notification:', message);
            } else if (type === 'warning') {
                console.log('Warning Notification:', message);
            } else if (type === 'info') {
                console.debug('Info Notification:', message);
            }
        } // ende von showNotification


    } catch (error) {
        console.error('Error in populateSelect or setFitSystem:', error);
    }
    // Event listener for nominal size input
    document.addEventListener("keydown", function (evt) {

        if (!htmlNominalSizeById) return;
        let value = parseFloat(htmlNominalSizeById.value) || 0;
        if (evt.key === '+') {
            htmlNominalSizeById.value = value + 1;
            htmlNominalSizeById.dispatchEvent(new Event('change'));
        } else if (evt.key === '-') {
            if (value > 1) {
                htmlNominalSizeById.value = value - 1;
                htmlNominalSizeById.dispatchEvent(new Event('change'));
            }
        }
    });

    // Event listener for fit-system-select select change, sets form data to readonly of selected system
    htmlFitSystemSelectById.addEventListener('change', function (evt) {
        const value = evt.target.value;

        if (value === 'hole') document.getElementById('fit-type-system-msg').innerText = 'Einheitsbohrung';
        else if (value === 'shaft') document.getElementById('fit-type-system-msg').innerText = 'Einheitswelle';
        else if (value === 'combined') document.getElementById('fit-type-system-msg').innerText = 'Kombiniertes System';

    });

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
                try {
                    
                    console.debug('Response Data:', response.data);
                    htmlNominalSizeById.value = response.data.Tolerance.nominal_size || '';

                    htmlFitSystemSelectById.value = response.data.Tolerance['fit-type-system-msg'] || '';
                    setFitSystem(htmlFitSystemSelectById.value);

                    // Set fit system and adjust form fields
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
                        document.getElementById('fit-type-msg').innerText = response.data.Tolerance['fit-type-msg'] === 'clearance' ? 'Spielpassung' : response.data.Tolerance['fit-type'] === 'interference' ? 'Übermaßpassung' : 'Übergangspassung';
                        if (response.data.Tolerance['fit-type-system-msg'] !== undefined) {
                            document.getElementById('fit-type-system-msg').innerText = document.getElementById('fit-system-select').options[document.getElementById('fit-system-select').selectedIndex].text;
                        }
                    } else {
                        // document.getElementById('IT').innerText = '--  µm';
                        // document.getElementById('it').innerText = '--  µm';
                    }


                    // Wenn Bohrungsdaten vorhanden, dann darstellen
                    if (response.data.Bore.results !== null) {
                        const objBore = response.data.Bore
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
                        const objShaft = response.data.Shaft
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

                    if (response.data.Drawing.image !== undefined && response.data.Drawing.image !== null && response.data.Drawing.image !== '') {
// console.log('Drawing Data:', response.data.Drawing);
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

                } catch (error) {
                    console.error('Fehler beim Verarbeiten der Antwortdaten:', error);
                }

            } // Ende if response.success

            // Erst nach einer erfolgreichen Anfrage das Diagramm zeichnen
            if (response.success) {
                const objBore = response.data.Bore
                const objShaft = response.data.Shaft
                const objTolerance = response.data.Tolerances

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

    // Fehlerbehandlung für htmx-Anfragen

    document.body.addEventListener('htmx:responseError', function (evt) {
    //     showNotification('error', 'Server error occurred');
    // });

    // document.body.addEventListener('htmx:error', function (evt) {

        const detail = evt.detail;
        let errorMessage = 'Ein unbekannter Fehler ist aufgetreten';

        if (detail.xhr) {
            const status = detail.xhr.status;

            switch(status) {
                case 400:
                    errorMessage = 'Bad request';
                    break;
                case 403:
                    errorMessage = 'Permission denied';
                    break;
                case 404:
                    errorMessage = 'Resource not found';
                    break;
                case 500:
                    errorMessage = 'Server error';
                    break;
                default:
                    errorMessage = `Error ${status}`;
            }

                // Try to parse JSON error response from Django
            try {
                const response = JSON.parse(detail.xhr.responseText);
                if (response.error) {
                    errorMessage = response.error;
                }
                if (response.message) {
                    errorMessage = response.message;
                }
            } catch (e) {
                // Not JSON response
            }
        }
        // console.log('htmx:error event:', evt);
        showNotification('error', errorMessage);
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
});
